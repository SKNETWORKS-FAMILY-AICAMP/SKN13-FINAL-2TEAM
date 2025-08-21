from fastapi import APIRouter, Request, Depends, Form
from dependencies import login_required
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from data_store import clothing_data
from sqlalchemy.orm import Session
from db import get_db
from models.models_auth import User
from crud.user_crud import (
    get_user_by_username,
    get_preference_by_user_id,
    upsert_user_preference,
    list_jjim_product_ids,
    remove_jjim,
    remove_jjim_bulk,
)
from crud.recommendation_crud import get_user_recommendations
from crud.chat_crud import get_user_chat_sessions, get_session_messages
from datetime import timedelta

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def mypage(request: Request, db: Session = Depends(get_db)):
    # 사용자 정보 가져오기
    user = get_user_by_username(db, request.session.get("user_name"))
    if not user:
        return RedirectResponse(url="/auth/login")
    
    # 1. 최근 추천받은 상품 (모든 추천 상품)
    recent_recommendations = get_user_recommendations(db, user.id, limit=50)
    recommended_products = []
    for rec in recent_recommendations:
        # clothing_data에서 해당 상품 찾기
        product = next((p for p in clothing_data if str(p.get('상품코드')) == str(rec.item_id)), None)
        if product:
            recommended_products.append({
                'product': product,
                'query': rec.query,
                'reason': rec.reason
            })
    
    # 2. 찜한 상품
    jjim_ids = list_jjim_product_ids(db, user.id)
    id_set = set(str(pid) for pid in jjim_ids)
    jjim_products = [p for p in clothing_data if str(p.get('상품코드')) in id_set]
    
    # 3. 대화 내역 (최근 3개)
    chat_sessions = get_user_chat_sessions(db, user.id, limit=3)
    chat_history = []
    for session in chat_sessions:
        messages = get_session_messages(db, session.id, user.id)
        if messages:
            # 딕셔너리 형태로 반환되므로 ['text']로 접근
            first_message = messages[0]['text'] if messages else ""
            last_response = messages[-1]['text'] if len(messages) > 1 else ""
            # 시간을 +9시간으로 조정
            adjusted_time = session.created_at + timedelta(hours=9)
            chat_history.append({
                'session_id': session.id,
                'session_name': session.session_name,
                'created_at': adjusted_time,
                'first_message': first_message[:50] + "..." if len(first_message) > 50 else first_message,
                'last_response': last_response[:50] + "..." if len(last_response) > 50 else last_response,
                'message_count': len(messages)
            })

    return templates.TemplateResponse("mypage/mypage.html", {
        "request": request,
        "recommended_products": recommended_products,
        "jjim_products": jjim_products,
        "chat_history": chat_history,
        "clothing_data": clothing_data
    })


@router.post("/jjim/remove", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def remove_my_jjim(request: Request, product_id: str = Form(...), db: Session = Depends(get_db)):
    user = get_user_by_username(db, request.session.get("user_name"))
    if not user:
        return {"success": False}
    ok = remove_jjim(db, user.id, product_id)
    return {"success": ok}


@router.post("/jjim/delete", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def delete_selected_jjim(request: Request, product_ids: str = Form(""), db: Session = Depends(get_db)):
    user = get_user_by_username(db, request.session.get("user_name"))
    if not user:
        return {"success": False}
    ids = [pid.strip() for pid in product_ids.split(',') if pid.strip()]
    deleted = remove_jjim_bulk(db, user.id, ids)
    return {"success": True, "deleted": deleted}


@router.get("/profile/me", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def get_my_profile(request: Request, db: Session = Depends(get_db)):
    username = request.session.get("user_name")
    user = get_user_by_username(db, username)
    if not user:
        return JSONResponse(status_code=404, content={"success": False, "message": "사용자를 찾을 수 없습니다."})
    pref = get_preference_by_user_id(db, user.id)
    return {
        "success": True,
        "user": {
            "username": user.username,
            "email": user.email,
            "gender": user.gender,
        },
        "preference": {
            "height": getattr(pref, "height", None),
            "weight": getattr(pref, "weight", None),
            "preferred_color": getattr(pref, "preferred_color", None),
            "preferred_style": getattr(pref, "preferred_style", None),
        }
    }


@router.post("/profile/update", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def update_my_profile(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(None),
    gender: str = Form(None),
    height: int = Form(None),
    weight: int = Form(None),
    preferred_color: str = Form(None),
    preferred_style: str = Form(None),
):
    username = request.session.get("user_name")
    user = get_user_by_username(db, username)
    if not user:
        return JSONResponse(status_code=404, content={"success": False, "message": "사용자를 찾을 수 없습니다."})

    # 기본 정보 업데이트
    if email:
        user.email = email
    user.gender = gender or user.gender
    db.add(user)
    db.commit()
    db.refresh(user)

    # 선호정보 업데이트
    upsert_user_preference(
        db,
        user_id=user.id,
        height=height,
        weight=weight,
        preferred_color=preferred_color,
        preferred_style=preferred_style,
    )

    return {"success": True, "message": "프로필이 업데이트되었습니다."}