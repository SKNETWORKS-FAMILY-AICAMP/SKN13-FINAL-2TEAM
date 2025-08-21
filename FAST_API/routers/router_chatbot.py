from fastapi import APIRouter, Form, Depends, Query
from fastapi.responses import JSONResponse
import pandas as pd
import random
import numpy as np
from typing import List, Dict, Optional
import json
from sqlalchemy.orm import Session

from db import get_db
from dependencies import login_required
from crud.user_crud import get_user_by_username
from crud.chat_crud import (
    create_chat_session,
    get_latest_chat_session,
    create_chat_message,
    get_conversation_context,
    get_user_chat_sessions,
    get_chat_session_by_id,
    update_session_name,
    delete_chat_session,
    get_session_messages,
    get_chat_history_for_llm
)
from services.llm_service import LLMService, LLMResponse
from services.clothing_recommender import recommend_clothing_by_weather
from utils.safe_utils import safe_lower, safe_str

router = APIRouter()

from data_store import clothing_data

# LLM 서비스 초기화 (LangGraph 기반)
llm_service = LLMService()

@router.post("/", response_class=JSONResponse)
async def chat_recommend(
    user_input: str = Form(...),
    session_id: Optional[int] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """챗봇 추천 API - LangGraph 기반 LLM Agent"""
    try:

        
        # 사용자 정보 가져오기
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "message": "사용자 정보를 찾을 수 없습니다.",
                "products": [],
                "analysis": {}
            })
        
        # 세션 처리
        if session_id:
            # 기존 세션 사용
            chat_session = get_chat_session_by_id(db, session_id, user.id)
            if not chat_session:
                return JSONResponse(content={
                    "message": "세션을 찾을 수 없습니다.",
                    "products": [],
                    "analysis": {}
                })
        else:
            # 새로운 세션 생성
            session_name = f"{user_input[:20]}{'...' if len(user_input) > 20 else ''}"
            chat_session = create_chat_session(db, user.id, session_name)
        
        # 사용자 메시지 저장
        user_message = create_chat_message(db, chat_session.id, "user", user_input)
        
        # LLM 서비스를 통해 처리 (LangGraph 기반)
        try:
            llm_response: LLMResponse = await llm_service.process_user_input(
                user_input=user_input,
                session_id=chat_session.id,
                user_id=user.id,
                available_products=clothing_data if clothing_data else [],
                db=db,
                latitude=latitude,
                longitude=longitude
            )
            
            message = llm_response.final_message
            products = llm_response.products
            analysis_info = {
                "intent": llm_response.analysis_result.intent,
                "always_uses_context": True,
                "confidence": getattr(llm_response.analysis_result, 'confidence', 1.0),
                "analysis_summary": getattr(llm_response.analysis_result, 'analysis_summary', 'N/A'),
                "filtering_conditions": getattr(llm_response.analysis_result, 'filtering_conditions', {}),
                "summary_info": {
                    "has_summary": bool(llm_response.summary_result and llm_response.summary_result.success),
                    "action_taken": llm_response.summary_result.action_taken if llm_response.summary_result else None,
                    "summary_text": llm_response.summary_result.summary_text if llm_response.summary_result else None
                } if llm_response.summary_result else {"has_summary": False}
            }
            

            
            # 날씨 의도 처리 및 의류 추천 통합 (기존 로직 유지)
            if llm_response.analysis_result.intent == "weather":
                try:
                    # 날씨 정보에서 기온 추출
                    temperature = None
                    weather_description = None
                    
                    # 메시지에서 기온 정보 추출
                    import re
                    temp_match = re.search(r'(\d+(?:\.\d+)?)°C', message)
                    if temp_match:
                        temperature = float(temp_match.group(1))
                    
                    # 날씨 상황 추출
                    weather_match = re.search(r'날씨 상황\*\*: (.+)', message)
                    if weather_match:
                        weather_description = weather_match.group(1).strip()
                    

                    
                    # 사용자 성별 처리
                    raw_gender = user.gender if hasattr(user, 'gender') else None
                    user_gender = "남성" if raw_gender == "male" else "여성" if raw_gender == "female" else "남성"
                    
                    if weather_description and temperature is not None:
                        # 의류 추천 생성
                        recommended_clothing = recommend_clothing_by_weather(weather_description, user_gender)
                        
                        # 추천 메시지 추가
                        if recommended_clothing and any(recommended_clothing.values()):
                            clothing_parts = []
                            for category, items in recommended_clothing.items():
                                if items:
                                    clothing_parts.append(f"{category}: {', '.join(items)}")
                            
                            if clothing_parts:
                                clothing_message = f"\n\n🎯 **오늘 날씨 추천**\n{', '.join(clothing_parts)}을(를) 추천해 드려요!"
                                message += clothing_message
                
                except Exception:
                    # 오류가 있어도 기본 날씨 정보는 제공
                    pass
            
        except Exception:
            
            # 오류 시 기본 응답
            message = f"'{user_input}'에 대한 추천을 처리하는 중 오류가 발생했습니다. 다시 시도해주세요."
            products = []
            analysis_info = {
                "intent": "error",
                "always_uses_context": True,
                "confidence": 0.0,
                "analysis_summary": "처리 중 오류 발생",
                "filtering_conditions": {}
            }
        
        # 통합 서머리 결과를 사용한 챗봇 응답 저장
        try:
            # LLM 응답에서 서머리 결과 추출
            summary_text = None
            if llm_response.summary_result and llm_response.summary_result.success:
                summary_text = llm_response.summary_result.summary_text
            
            # 챗봇 응답 저장 (통합 서머리와 함께)
            bot_message = create_chat_message(db, chat_session.id, "bot", message, summary_text)
            
        except Exception:
            # 오류 시 서머리 없이 메시지만 저장
            bot_message = create_chat_message(db, chat_session.id, "bot", message)
        
        # 응답 구성
        response_data = {
            "message": message,
            "products": products,
            "session_id": chat_session.id,
            "session_name": chat_session.session_name,
            "analysis": analysis_info
        }
        
        # Q/A 요약 정보 추가 (디버깅용)
        if session_id:
            from crud.chat_crud import get_recent_qa_summaries
            qa_summaries = get_recent_qa_summaries(db, chat_session.id, limit=3)
            if qa_summaries:
                response_data["recent_qa_summaries"] = qa_summaries
        
        return JSONResponse(content=response_data)
        
    except Exception:
        return JSONResponse(content={
            "message": "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.",
            "products": [],
            "analysis": {"error": "처리 중 오류 발생"}
        })

@router.get("/analysis/{session_id}", response_class=JSONResponse)
async def get_session_analysis(
    session_id: int,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """세션 분석 정보 조회"""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "analysis": {}
            })
        
        # 세션 정보 조회
        session = get_chat_session_by_id(db, session_id, user.id)
        if not session:
            return JSONResponse(content={
                "success": False,
                "message": "세션을 찾을 수 없습니다.",
                "analysis": {}
            })
        
        # 메시지 수 계산
        messages = get_session_messages(db, session_id, user.id)
        
        # 최근 Q/A 요약들 가져오기
        from crud.chat_crud import get_recent_qa_summaries
        qa_summaries = get_recent_qa_summaries(db, session.id, limit=5)
        
        # 분석 정보 구성
        analysis_info = {
            "session_id": session.id,
            "session_name": session.session_name,
            "recent_qa_summaries": qa_summaries,
            "message_count": len(messages),
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None
        }
        
        return JSONResponse(content={
            "success": True,
            "message": "세션 분석 정보를 성공적으로 조회했습니다.",
            "analysis": analysis_info
        })
        
    except Exception as e:
        print(f"세션 분석 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 분석 조회 중 오류가 발생했습니다.",
            "analysis": {}
        })

@router.get("/session/{session_id}/qa-summaries", response_class=JSONResponse)
async def get_session_qa_summaries(
    session_id: int,
    limit: int = Query(10, description="가져올 요약 수"),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """세션의 Q/A 요약들을 조회합니다"""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "summaries": []
            })
        
        # 세션 권한 확인
        session = get_chat_session_by_id(db, session_id, user.id)
        if not session:
            return JSONResponse(content={
                "success": False,
                "message": "세션을 찾을 수 없거나 권한이 없습니다.",
                "summaries": []
            })
        
        # Q/A 요약들 가져오기
        from crud.chat_crud import get_recent_qa_summaries
        qa_summaries = get_recent_qa_summaries(db, session_id, limit=limit)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Q/A 요약 {len(qa_summaries)}개를 성공적으로 조회했습니다.",
            "summaries": qa_summaries
        })
        
    except Exception as e:
        print(f"Q/A 요약 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "Q/A 요약 조회 중 오류가 발생했습니다.",
            "summaries": []
        })



# 기존 엔드포인트들도 유지 (하위 호환성)
@router.get("/sessions", response_class=JSONResponse)
async def get_chat_sessions(
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """사용자의 모든 챗봇 세션을 조회합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "sessions": []
            })
        
        sessions = get_user_chat_sessions(db, user.id, limit=50)
        
        session_list = []
        for session in sessions:
            # 각 세션의 메시지 수 계산
            messages = get_session_messages(db, session.id, user.id)
            
            # 최근 Q/A 요약 가져오기
            from crud.chat_crud import get_recent_qa_summaries
            qa_summaries = get_recent_qa_summaries(db, session.id, limit=1)
            latest_summary = qa_summaries[0][:50] + "..." if qa_summaries and len(qa_summaries[0]) > 50 else qa_summaries[0] if qa_summaries else None
            
            session_list.append({
                "id": session.id,
                "name": session.session_name,
                "latest_qa_summary": latest_summary,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "message_count": len(messages)
            })
        
        return JSONResponse(content={
            "success": True,
            "message": "세션 목록을 성공적으로 조회했습니다.",
            "sessions": session_list
        })
        
    except Exception as e:
        print(f"세션 목록 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 목록 조회 중 오류가 발생했습니다.",
            "sessions": []
        })

@router.get("/session/{session_id}/messages", response_class=JSONResponse)
async def get_session_messages_api(
    session_id: int,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """특정 세션의 메시지들을 조회합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "messages": []
            })
        
        messages = get_session_messages(db, session_id, user.id)
        
        return JSONResponse(content={
            "success": True,
            "message": "세션 메시지를 성공적으로 조회했습니다.",
            "messages": messages
        })
        
    except Exception as e:
        print(f"세션 메시지 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 메시지 조회 중 오류가 발생했습니다.",
            "messages": []
        })

@router.put("/session/{session_id}/name", response_class=JSONResponse)
async def update_session_name_api(
    session_id: int,
    new_name: str = Form(...),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """세션 이름을 변경합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다."
            })
        
        success = update_session_name(db, session_id, user.id, new_name)
        
        if success:
            return JSONResponse(content={
                "success": True,
                "message": "세션 이름이 성공적으로 변경되었습니다."
            })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "세션을 찾을 수 없거나 권한이 없습니다."
            })
        
    except Exception as e:
        print(f"세션 이름 변경 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 이름 변경 중 오류가 발생했습니다."
        })

@router.delete("/session/{session_id}", response_class=JSONResponse)
async def delete_session_api(
    session_id: int,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """세션을 삭제합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다."
            })
        
        success = delete_chat_session(db, session_id, user.id)
        
        if success:
            return JSONResponse(content={
                "success": True,
                "message": "세션이 성공적으로 삭제되었습니다."
            })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "세션을 찾을 수 없거나 권한이 없습니다."
            })
        
    except Exception as e:
        print(f"세션 삭제 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 삭제 중 오류가 발생했습니다."
        })
