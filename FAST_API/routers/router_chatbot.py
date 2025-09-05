from fastapi import APIRouter, Form, Depends, File, UploadFile, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import uuid
import tempfile
import os
from typing import List, Dict, Optional

from db import get_db
from dependencies import login_required, get_category_info
from crud.user_crud import get_user_by_username
from crud.chat_crud import (
    create_chat_session,
    create_chat_message,
    get_chat_session_by_id,
    get_session_messages,
    cleanup_user_expired_sessions,
    cleanup_old_sessions_if_needed
)
from services.llm_service import LLMService, LLMResponse
from image_recommender import get_subcategory_from_gpt, recommend_by_image
# clothing_recommender는 삭제되었으므로 WeatherAgent의 메서드 사용
from utils.safe_utils import safe_lower, safe_str
from image_recommender import recommend_by_image

router = APIRouter()
from data_store import clothing_data

router = APIRouter()
llm_service = LLMService()


async def handle_image_recommendation(
    image_bytes: bytes, 
    user_input: str, 
    db: Session, 
    user_id: int, 
    session_id: str
) -> dict:
    """이미지 추천 로직을 처리하고 응답 데이터를 반환합니다."""
    major_cat, sub_cat = await get_category_info(user_input)

    if not major_cat:
        return {"message": "카테고리를 이해하지 못했어요. '상의', '하의', '드레스' 또는 '후드티'와 같이 입력해주세요.", "products": []}

    if not sub_cat:
        sub_cat = await get_subcategory_from_gpt(image_bytes, major_cat)
        if not sub_cat or sub_cat == "unknown":
            return {"message": f"{major_cat.capitalize()} 종류를 이미지에서 찾지 못했습니다. 더 선명한 이미지를 사용해보세요.", "products": []}

    result = await recommend_by_image(image_bytes, major_cat, sub_cat)

    if "error" in result:
        return {"message": result["error"], "products": []}

    recommendations = result.get("recommendations", [])
    products = [
        {
            "상품코드": r.get("id"),
            "상품명": r.get("payload", {}).get("product_name", "정보 없음"),
            "가격": r.get("payload", {}).get("price", 0),
            "사진": r.get("payload", {}).get("image_url", ""),
        } for r in recommendations
    ]
    
    info_text = result.get("information", "")
    message = f"'{sub_cat}'와(과) 유사한 상품을 추천해 드립니다."
    
    response_data = {"message": message, "products": products, "analysis": {"information": info_text}}
    
    try:
        from crud.recommendation_crud import create_multiple_recommendations
        rec_data = [{"item_id": p["상품코드"], "query": user_input, "reason": f"이미지 추천 - {user_input}"} for p in products]
        created_recs = create_multiple_recommendations(db, user_id, rec_data)
        recommendation_ids = [rec.id for rec in created_recs]
        for i, product in enumerate(products):
            if i < len(recommendation_ids):
                product['recommendation_id'] = recommendation_ids[i]
        response_data['recommendation_id'] = recommendation_ids
    except Exception as e:
        print(f"이미지 추천 결과 저장 실패: {e}")

    return response_data


@router.post("/", response_class=JSONResponse)
async def chat_recommend(
    request: Request,
    user_input: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """챗봇 메인 API (이미지 처리 기능 통합)"""
    user = get_user_by_username(db, user_name)
    if not user:
        return JSONResponse(content={"message": "사용자 정보를 찾을 수 없습니다.", "products": []})

    # --- 세션 관리 ---
    if session_id and (chat_session := get_chat_session_by_id(db, session_id, user.id)):
        pass
    else:
        try:
            cleanup_user_expired_sessions(db, user.id, days=30)
            cleanup_old_sessions_if_needed(db, user.id, max_sessions=50)
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
            print(f"세션 정리 중 오류: {e}")
        session_name_prefix = user_input or "이미지 추천"
        session_name = f"{session_name_prefix[:20]}{'...' if len(session_name_prefix) > 20 else ''}"
        chat_session = create_chat_session(db, user.id, session_name)
    
    session_id = str(chat_session.id)

    # --- 로직 분기 ---
    # Case 1: 이미지가 새로 업로드된 경우
    if image:
        image_bytes = await image.read()
        create_chat_message(db, session_id, "user", user_input or "(이미지 업로드)")

        if user_input:
            # Case 1a: Image + Text
            response_data = await handle_image_recommendation(image_bytes, user_input, db, user.id, session_id)
        else:
            # Case 1b: Image only -> Ask for category
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"{session_id}_{uuid.uuid4()}.jpg")
            with open(temp_path, "wb") as f:
                f.write(image_bytes)
            
            chat_session.pending_image_path = temp_path
            db.commit()
            
            response_data = {"message": "어떤 종류의 의류를 추천해 드릴까요? (예: 상의, 후드티, 드레스)", "products": []}
        
        create_chat_message(db, session_id, "bot", response_data["message"], products_data=response_data.get("products"))
        response_data["session_id"] = session_id
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

    # Case 2: 텍스트만 입력된 경우
    if not user_input:
        return JSONResponse(content={"message": "메시지를 입력해주세요.", "products": [], "session_id": session_id})

    create_chat_message(db, session_id, "user", user_input)

    # Case 2a: Text is a response to an image query
    if chat_session.pending_image_path and os.path.exists(chat_session.pending_image_path):
        image_path = chat_session.pending_image_path
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        response_data = await handle_image_recommendation(image_bytes, user_input, db, user.id, session_id)
        
        chat_session.pending_image_path = None # Clear path after use
        db.commit()
        os.remove(image_path) # Clean up temp file

        create_chat_message(db, session_id, "bot", response_data["message"], products_data=response_data.get("products"))
        response_data["session_id"] = session_id
        return JSONResponse(content=response_data)
    
    # Case 2b: Normal text chat
    try:
        llm_response: LLMResponse = await llm_service.process_user_input(
            user_input=user_input, session_id=session_id, user_id=user.id,
            available_products=clothing_data, db=db, latitude=latitude, longitude=longitude
        )
        message = llm_response.final_message
        products = llm_response.products
        analysis_info = {"intent": llm_response.analysis_result.intent, "confidence": getattr(llm_response.analysis_result, 'confidence', 1.0)}
        
        summary_text = llm_response.summary_result.summary_text if llm_response.summary_result and llm_response.summary_result.success else None
        create_chat_message(db, session_id, "bot", message, summary=summary_text, products_data=products)
        return JSONResponse(content={
            "message": message, "products": products, "session_id": session_id, "analysis": analysis_info
        })

    except Exception as e:
        logger.error(f"텍스트 챗봇 오류: {e}")
        message = "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요."
        create_chat_message(db, session_id, "bot", message)
        return JSONResponse(content={"message": message, "products": [], "session_id": session_id})


@router.get("/session/{session_id}/messages", response_class=JSONResponse)
async def get_session_messages_api(session_id: str, db: Session = Depends(get_db), user_name: str = Depends(login_required)):
    user = get_user_by_username(db, user_name)
    if not user:
        return JSONResponse(content={"success": False, "message": "사용자 정보를 찾을 수 없습니다.", "messages": []})
    from crud.chat_crud import get_chat_message_with_recommendations
    messages = get_chat_message_with_recommendations(db, session_id, user.id)
    return JSONResponse(content={"success": True, "message": "메시지를 성공적으로 가져왔습니다.", "messages": messages})


@router.post("/feedback", response_class=JSONResponse)
async def submit_feedback(recommendation_id: List[str] = Form(...), feedback_rating: int = Form(...), feedback_reason: str = Form(""), db: Session = Depends(get_db), user_name: str = Depends(login_required)):
    user = get_user_by_username(db, user_name)
    if not user:
        return JSONResponse(content={"success": False, "message": "사용자 정보를 찾을 수 없습니다."})
    from crud.recommendation_crud import update_recommendation_feedback
    success_count = 0
    for rec_id in recommendation_id:
        try:
            success = update_recommendation_feedback(db, int(rec_id), user.id, feedback_rating, feedback_reason)
            if success: success_count += 1
        except ValueError:
            continue
    if success_count > 0:
        return JSONResponse(content={"success": True, "message": f"{success_count}개의 추천 결과에 피드백이 저장되었습니다."})
    else:
        return JSONResponse(content={"success": False, "message": "피드백 저장에 실패했습니다."})
