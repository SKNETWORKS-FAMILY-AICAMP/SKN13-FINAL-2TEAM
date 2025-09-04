from fastapi import APIRouter, Form, Depends, Query, File, UploadFile
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
# clothing_recommender는 삭제되었으므로 WeatherAgent의 메서드 사용
from utils.safe_utils import safe_lower, safe_str
from image_recommender import recommend_by_image

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
                        # WeatherAgent를 통해 의류 추천 (개선된 메서드 사용)
                        from services.agents.weather_agent import WeatherAgent
                        weather_agent = WeatherAgent()
                        # 날씨 데이터가 없는 경우 기본 추천
                        recommended_clothing = await weather_agent.recommend_clothing_by_weather(
                            weather_description, 
                            user_gender,
                            weather_data=None,  # 챗봇에서는 날씨 데이터가 제한적
                            location="현재 위치"
                        )
                        
                        # 추천 메시지 추가 (새로운 JSON 구조 지원)
                        if recommended_clothing and any(recommended_clothing.values()):
                            # 새로운 JSON 구조 확인
                            recommendations = recommended_clothing.get("recommendations", [])
                            
                            if recommendations:
                                # 새로운 구조: 의미적으로 연결된 조합
                                clothing_message = f"\n\n🎯 **오늘 날씨 추천**\n"
                                for i, rec in enumerate(recommendations, 1):
                                    item = rec.get("item", "")
                                    style = rec.get("style", "")
                                    color = rec.get("color", "")
                                    reason = rec.get("reason", "")
                                    
                                    clothing_message += f"**{i}. {item}**\n"
                                    if style:
                                        clothing_message += f"   🎨 스타일: {style}\n"
                                    if color:
                                        clothing_message += f"   🌈 색상: {color}\n"
                                    if reason:
                                        clothing_message += f"   💡 이유: {reason}\n"
                                    clothing_message += "\n"
                                
                                message += clothing_message
                            else:
                                # 기존 구조 지원 (fallback)
                                clothing_parts = []
                                
                                # 카테고리 표시
                                categories = recommended_clothing.get("categories", [])
                                if categories:
                                    clothing_parts.append(f"카테고리: {', '.join(categories)}")
                                
                                # 구체적인 아이템 표시
                                specific_items = recommended_clothing.get("specific_items", [])
                                if specific_items:
                                    clothing_parts.append(f"추천 아이템: {', '.join(specific_items)}")
                                
                                # 색상 표시
                                colors = recommended_clothing.get("colors", [])
                                if colors:
                                    clothing_parts.append(f"추천 색상: {', '.join(colors)}")
                                
                                # 스타일 표시
                                styles = recommended_clothing.get("styles", [])
                                if styles:
                                    clothing_parts.append(f"추천 스타일: {', '.join(styles)}")
                                
                                # 추천이유 추출
                                recommendation_reasons = recommended_clothing.get("추천이유", [])
                                reason_text = ""
                                if recommendation_reasons:
                                    reason_text = f"\n💡 **추천 이유**: {' '.join(recommendation_reasons)}"
                                
                                if clothing_parts:
                                    clothing_message = f"\n\n🎯 **오늘 날씨 추천**{reason_text}\n{', '.join(clothing_parts)}을(를) 추천해 드려요!"
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
            recommendation_ids = []
            if products and len(products) > 0:
                try:
                    from crud.recommendation_crud import create_multiple_recommendations, update_recommendation_feedback, get_user_recommendations
                    
                    # 최근 추천 기록 조회하여 중복 체크 (더 많은 기록 조회)
                    recent_recommendations = get_user_recommendations(db, user.id, limit=50)
                    recent_item_ids = {rec.item_id for rec in recent_recommendations}
                    
                    recommendations_data = []
                    for product in products:
                        item_id = product.get("상품코드", product.get("상품ID", 0))
                        if item_id and item_id not in recent_item_ids:
                            recommendations_data.append({
                                "item_id": item_id,
                                "query": user_input,
                                "reason": f"챗봇 추천 - {user_input}"
                            })
                            recent_item_ids.add(item_id)  # 중복 방지를 위해 추가
                        else:
                            print(f"ℹ️ 상품 {item_id}는 이미 추천되어 저장하지 않습니다.")
                    
                    if recommendations_data:
                        created_recommendations = create_multiple_recommendations(db, user.id, recommendations_data)
                        # 각 상품별로 개별적인 추천 ID를 생성
                        if created_recommendations:
                            # 각 상품에 개별적인 추천 ID 할당
                            for i, product in enumerate(products):
                                if i < len(created_recommendations):
                                    product['recommendation_id'] = created_recommendations[i].id
                            
                            # 모든 추천 ID를 리스트로 수집
                            recommendation_ids = [str(rec.id) for rec in created_recommendations]
                            print(f"✅ 추천 결과 {len(created_recommendations)}개를 저장하고 각 상품별로 개별 추천 ID를 할당했습니다.")
                    else:
                        print("⚠️ 저장할 추천 결과가 없습니다 (중복 제거 후).")
                        recommendation_ids = []
                except Exception as e:
                    print(f"❌ 추천 결과 저장 중 오류: {e}")
                    recommendation_ids = []
            
            # 챗봇 응답 저장 (상품 데이터와 추천 ID 함께)
            bot_message = create_chat_message(
                db, 
                str(chat_session.id), 
                "bot", 
                message, 
                summary_text, 
                recommendation_ids,  # 리스트 형태로 전달
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
            "recommendation_id": recommendation_ids  # 추천 ID 추가
        }
        
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
    recommendation_id: List[str] = Form(...),  # int → List[str]로 변경
    feedback_rating: int = Form(...),
    feedback_reason: str = Form(""),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """추천 결과에 대한 피드백을 제출합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={"success": False, "message": "사용자 정보를 찾을 수 없습니다."})
        
        print(f"피드백 요청 받음: recommendation_id={recommendation_id}, rating={feedback_rating}, reason={feedback_reason}")
        print(f"데이터 타입: recommendation_id={type(recommendation_id)}, rating={type(feedback_rating)}")
        
        # 피드백 처리
        from crud.recommendation_crud import update_recommendation_feedback
        
        success_count = 0
        for rec_id in recommendation_id:
            try:
                rec_id_int = int(rec_id)
                success = update_recommendation_feedback(
                    db, 
                    rec_id_int, 
                    user.id, 
                    feedback_rating, 
                    feedback_reason
                )
                if success:
                    success_count += 1
                    print(f"추천 ID: {rec_id}")
            except ValueError:
                print(f"잘못된 추천 ID 형식: {rec_id}")
                continue
        
        if success_count > 0:
            return JSONResponse(content={
                "success": True, 
                "message": f"{success_count}개의 추천 결과에 피드백이 저장되었습니다."
            })
        else:
            return JSONResponse(content={
                "success": False, 
                "message": "피드백 저장에 실패했습니다."
            })
            
    except Exception as e:
        print(f"피드백 처리 중 오류: {e}")
        return JSONResponse(content={
            "success": False, 
            "message": "피드백 처리 중 오류가 발생했습니다."
        })

@router.post("/image-recommend", response_class=JSONResponse)
async def chat_image_recommend(image: UploadFile = File(...)):
    """챗봇 추천 API - 이미지 기반"""
    try:
        image_bytes = await image.read()
        result = recommend_by_image(image_bytes)

        if "error" in result:
            return JSONResponse(content={"message": result["error"], "products": []})

        # 테스트용: information 텍스트를 메시지에 추가
        info_text = result.get("information", "정보 텍스트를 가져올 수 없습니다.")
        message = f"[생성된 정보 텍스트]:\n{info_text}\n\n이미지와 유사한 상품을 추천해 드립니다."

        # Qdrant에서 받은 데이터(id, payload)를 기반으로 상품 정보를 조회해야 할 수 있음
        # 현재는 받은 payload를 그대로 반환
        recommendations = result.get("recommendations", [])
        products = [
            {
                "상품코드": r.get("id"),
                "상품명": r.get("information", "").split('|')[0].split('=')[-1], # payload에서 정보 추출 (임시)
                "가격": "정보 없음",
                "사진": r.get("payload", {}).get("image_url", ""), # payload에 이미지 URL이 있다고 가정
            } for r in recommendations
        ]

        info_text = result.get("information", "정보 텍스트를 가져올 수 없습니다.")
        message = f"[생성된 정보 텍스트]:\n{info_text}\n\n이미지 기반 추천이 완료되었습니다."

        return JSONResponse(content={
            "message": message,
            "products": products
        })

    except Exception as e:
        print(f"이미지 챗봇 오류: {e}")
        return JSONResponse(content={
            "message": "이미지 처리 중 오류가 발생했습니다.",
            "products": []
        })
