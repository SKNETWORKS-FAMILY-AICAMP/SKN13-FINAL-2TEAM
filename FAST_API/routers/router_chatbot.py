from fastapi import APIRouter, Form, Depends, File, UploadFile, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import uuid
import tempfile
import os
from typing import List, Dict, Optional
import traceback # ADDED

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
    # 1. 기본값 초기화
    message = "죄송합니다. 요청을 처리하는 중 오류가 발생했습니다."
    products: list = []
    analysis_info: dict = {}
    recommendation_ids: list = []
    
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
            session_name_prefix = user_input or "새 대화"
            session_name = f"{session_name_prefix[:20]}{'...' if len(session_name_prefix) > 20 else ''}"
            chat_session = create_chat_session(db, user.id, session_name)
        except Exception as e:
            print(f"세션 생성 오류: {e}")
            return JSONResponse(content={"message": "채팅 세션을 시작하는 데 실패했습니다.", "products": []})

    session_id = str(chat_session.id)

    # --- 로직 분기 ---
    # Case 1: 이미지가 새로 업로드된 경우
    if image:
        image_bytes = await image.read()
        create_chat_message(db, session_id, "user", user_input or "(이미지 업로드)")

        if user_input:
            response_data = await handle_image_recommendation(image_bytes, user_input, db, user.id, session_id)
            message = response_data.get("message", "이미지 분석 결과입니다.")
            products = response_data.get("products", [])
            analysis_info = response_data.get("analysis", {})
            recommendation_ids = response_data.get("recommendation_id", [])
        else:
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"{session_id}_{uuid.uuid4()}.jpg")
            with open(temp_path, "wb") as f:
                f.write(image_bytes)
            
            chat_session.pending_image_path = temp_path
            db.commit()
            
            message = "어떤 종류의 의류를 추천해 드릴까요? (예: 상의, 후드티, 드레스)"
        
        create_chat_message(db, session_id, "bot", message, products_data=products, recommendation_id=recommendation_ids)
        return JSONResponse(content={
            "message": message, "products": products, "session_id": session_id, 
            "analysis": analysis_info, "recommendation_id": recommendation_ids
        })

    # Case 2: 텍스트만 입력된 경우
    if not user_input:
        return JSONResponse(content={"message": "메시지를 입력해주세요.", "products": [], "session_id": session_id})

    create_chat_message(db, session_id, "user", user_input)

    if chat_session.pending_image_path and os.path.exists(chat_session.pending_image_path):
        image_path = chat_session.pending_image_path
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        response_data = await handle_image_recommendation(image_bytes, user_input, db, user.id, session_id)
        chat_session.pending_image_path = None
        db.commit()
        os.remove(image_path)

        create_chat_message(db, session_id, "bot", response_data.get("message"), products_data=response_data.get("products"), recommendation_id=response_data.get("recommendation_id", []))
        response_data["session_id"] = session_id
        return JSONResponse(content=response_data)
    
    try:
        llm_response: LLMResponse = await llm_service.process_user_input(
            user_input=user_input, session_id=session_id, user_id=user.id,
            available_products=clothing_data, db=db, latitude=latitude, longitude=longitude
        )
        message = llm_response.final_message
        products = llm_response.products
        analysis_info = {"intent": llm_response.analysis_result.intent, "confidence": getattr(llm_response.analysis_result, 'confidence', 1.0)}
        
        if products:
            from crud.recommendation_crud import create_multiple_recommendations, get_user_recommendations
            recent_recommendations = get_user_recommendations(db, user.id, limit=50)
            recent_item_ids = {rec.item_id for rec in recent_recommendations}
            
            new_recs_data = [
                {"item_id": p.get("상품코드") or p.get("id"), "query": user_input, "reason": f"챗봇 추천 - {user_input}"}
                for p in products if (p.get("상품코드") or p.get("id")) and (p.get("상품코드") or p.get("id")) not in recent_item_ids
            ]
            
            if new_recs_data:
                created_recs = create_multiple_recommendations(db, user.id, new_recs_data)
                rec_map = {rec.item_id: rec.id for rec in created_recs}
                for p in products:
                    item_id = p.get("상품코드") or p.get("id")
                    if item_id in rec_map:
                        p['recommendation_id'] = rec_map[item_id]
                recommendation_ids = [str(rec_id) for rec_id in rec_map.values()]
                print(f"✅ {len(created_recs)}개의 새로운 추천을 저장했습니다.")
            else:
                message += "\n\nℹ️ 이전에 추천해 드렸던 상품들이 포함되어 있네요. 새로운 상품을 원하시면 더 구체적으로 말씀해주세요!"
                print("⚠️ 저장할 새로운 추천 상품이 없습니다 (모두 중복).")

        summary_text = llm_response.summary_result.summary_text if llm_response.summary_result and llm_response.summary_result.success else None
        create_chat_message(db, session_id, "bot", message, summary=summary_text, products_data=products, recommendation_id=recommendation_ids)
        
        return JSONResponse(content={
            "message": message, "products": products, "session_id": session_id, 
            "analysis": analysis_info, "recommendation_id": recommendation_ids
        })

    except Exception as e:
        print(f"텍스트 챗봇 오류: {e}")
        traceback.print_exc() # ADDED: Print full traceback
        error_message = "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요."
        create_chat_message(db, session_id, "bot", error_message)
        return JSONResponse(content={"message": error_message, "products": [], "session_id": session_id})


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
    error_details = []
    
    for rec_id in recommendation_id:
        try:
            rec_id_int = int(rec_id)
            success = update_recommendation_feedback(db, rec_id_int, user.id, feedback_rating, feedback_reason)
            if success: 
                success_count += 1
            else:
                error_details.append(f"추천 ID {rec_id} 처리 실패")
        except ValueError as e:
            error_details.append(f"추천 ID {rec_id} 형식 오류: {e}")
            continue
        except Exception as e:
            error_details.append(f"추천 ID {rec_id} 처리 중 오류: {e}")
            continue
    
    if success_count > 0:
        message = f"{success_count}개의 추천 결과에 피드백이 저장되었습니다."
        if error_details:
            message += f" (오류: {', '.join(error_details)})"
        return JSONResponse(content={"success": True, "message": message})
    else:
        error_message = "피드백 저장에 실패했습니다."
        if error_details:
            error_message += f" 상세: {', '.join(error_details)}"
        return JSONResponse(content={"success": False, "message": error_message})
