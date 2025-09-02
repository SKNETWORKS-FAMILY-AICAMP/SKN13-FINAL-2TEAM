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
    get_chat_history_for_llm,
    get_chat_session_by_id,
    get_session_messages,
    cleanup_user_expired_sessions,
    cleanup_old_sessions_if_needed
)
from models.recommendation import Recommendation
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
    session_id: Optional[str] = Form(None),
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
        
        # 세션 처리 (저장 기능 유지)
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
            # 새로운 세션 생성 전에 정리 작업 수행
            try:
                # 30일이 지난 세션들 자동 삭제
                expired_count = cleanup_user_expired_sessions(db, user.id, days=30)
                if expired_count > 0:
                    print(f"사용자 {user.id}의 만료된 세션 {expired_count}개 삭제됨")
                
                # 세션이 50개를 넘으면 오래된 것들 삭제
                cleaned_count = cleanup_old_sessions_if_needed(db, user.id, max_sessions=50)
                if cleaned_count > 0:
                    print(f"사용자 {user.id}의 오래된 세션 {cleaned_count}개 삭제됨")
            except Exception as e:
                print(f"세션 정리 중 오류 발생: {e}")
            
            # 새로운 세션 생성
            session_name = f"{user_input[:20]}{'...' if len(user_input) > 20 else ''}"
            chat_session = create_chat_session(db, user.id, session_name)
        
        # 사용자 메시지 저장
        user_message = create_chat_message(db, str(chat_session.id), "user", user_input)
        
        # LLM 서비스를 통해 처리 (LangGraph 기반)
        try:
            llm_response: LLMResponse = await llm_service.process_user_input(
                user_input=user_input,
                session_id=str(chat_session.id),
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
            
            # 추천 결과가 있으면 Recommendation 테이블에 저장 (기존 방식 유지)
            recommendation_id = None
            if products and len(products) > 0:
                try:
                    from crud.recommendation_crud import create_multiple_recommendations, update_recommendation_feedback
                    
                    recommendations_data = []
                    for product in products:
                        item_id = product.get("상품코드", product.get("상품ID", 0))
                        if item_id:
                            recommendations_data.append({
                                "item_id": item_id,
                                "query": user_input,
                                "reason": f"챗봇 추천 - {user_input}"
                            })
                    
                    if recommendations_data:
                        created_recommendations = create_multiple_recommendations(db, user.id, recommendations_data)
                        # 각 상품별로 개별적인 추천 ID를 생성
                        if created_recommendations:
                            # 각 상품에 개별적인 추천 ID 할당
                            for i, product in enumerate(products):
                                if i < len(created_recommendations):
                                    product['recommendation_id'] = created_recommendations[i].id
                            
                            recommendation_id = created_recommendations[0].id  # 메시지 연결용 (첫 번째 ID)
                            print(f"✅ 추천 결과 {len(created_recommendations)}개를 저장하고 각 상품별로 개별 추천 ID를 할당했습니다.")
                except Exception as e:
                    print(f"❌ 추천 결과 저장 중 오류: {e}")
            
            # 챗봇 응답 저장 (상품 데이터와 추천 ID 함께)
            bot_message = create_chat_message(
                db, 
                str(chat_session.id), 
                "bot", 
                message, 
                summary_text, 
                recommendation_id,
                products if products else None  # 상품 데이터를 JSON으로 저장
            )
            
        except Exception as e:
            print(f"❌ 챗봇 응답 저장 중 오류: {e}")
            # 오류 시 상품 데이터 없이 메시지만 저장
            bot_message = create_chat_message(db, str(chat_session.id), "bot", message)
        
        # 응답 구성
        response_data = {
            "message": message,
            "products": products,
            "session_id": str(chat_session.id),
            "session_name": chat_session.session_name,
            "analysis": analysis_info,
            "recommendation_id": recommendation_id  # 추천 ID 추가
        }
        
        print(f"챗봇 응답 데이터: {response_data}")
        print(f"recommendation_id 값: {response_data.get('recommendation_id')}")
        return JSONResponse(content=response_data)
        
    except Exception:
        return JSONResponse(content={
            "message": "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.",
            "products": [],
            "analysis": {"error": "처리 중 오류 발생"}
        })

@router.get("/session/{session_id}/messages", response_class=JSONResponse)
async def get_session_messages_api(
    session_id: str,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """챗봇 세션의 메시지와 추천 결과를 함께 가져옵니다."""
    try:
        # 사용자 정보 가져오기
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "messages": []
            })
        
        # 세션 메시지와 추천 결과 조회
        from crud.chat_crud import get_chat_message_with_recommendations
        messages = get_chat_message_with_recommendations(db, session_id, user.id)
        
        return JSONResponse(content={
            "success": True,
            "message": "메시지를 성공적으로 가져왔습니다.",
            "messages": messages
        })
        
    except Exception as e:
        print(f"세션 메시지 조회 중 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "메시지를 가져오는 중 오류가 발생했습니다.",
            "messages": []
        })

@router.post("/feedback", response_class=JSONResponse)
async def submit_feedback(
    recommendation_id: int = Form(...),
    feedback_rating: int = Form(...),  # 1: 좋아요, 0: 싫어요
    feedback_reason: str = Form(""),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """챗봇 추천에 대한 피드백을 제출합니다."""
    print(f"피드백 요청 받음: recommendation_id={recommendation_id}, rating={feedback_rating}, reason={feedback_reason}")
    print(f"사용자: {user_name}")
    print(f"데이터 타입: recommendation_id={type(recommendation_id)}, rating={type(feedback_rating)}")
    try:
        # 피드백 함수 import
        from crud.recommendation_crud import update_recommendation_feedback
        
        # 사용자 정보 가져오기
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다."
            })
        
        # 피드백 유효성 검사
        if feedback_rating not in [0, 1]:
            return JSONResponse(content={
                "success": False,
                "message": "잘못된 피드백 값입니다. (0: 싫어요, 1: 좋아요)"
            })
        
        print(f"사용자 ID: {user.id}")
        print(f"추천 ID: {recommendation_id}")
        print(f"피드백 레이팅: {feedback_rating}")
        print(f"피드백 이유: {feedback_reason}")
        
        # 피드백 업데이트
        success = update_recommendation_feedback(
            db=db,
            recommendation_id=recommendation_id,
            user_id=user.id,
            feedback_rating=feedback_rating,
            feedback_reason=feedback_reason if feedback_reason.strip() else None
        )
        
        print(f"피드백 업데이트 결과: {success}")
        
        if success:
            # 피드백 타입을 구분
            if feedback_reason and feedback_reason.strip():  # 코멘트가 있는 경우
                return JSONResponse(content={
                    "success": True,
                    "message": "코멘트가 성공적으로 저장되었습니다.",
                    "already_feedback": False,
                    "feedback_type": "comment"
                })
            else:  # 일반 피드백만 있는 경우
                return JSONResponse(content={
                    "success": True,
                    "message": "피드백이 성공적으로 저장되었습니다.",
                    "already_feedback": False,
                    "feedback_type": "rating"
                })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "추천 기록을 찾을 수 없습니다."
            })
            
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "message": f"피드백 저장 중 오류가 발생했습니다: {str(e)}"
        })
