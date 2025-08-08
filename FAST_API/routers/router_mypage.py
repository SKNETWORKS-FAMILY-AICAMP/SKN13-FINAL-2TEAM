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

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def mypage(request: Request, db: Session = Depends(get_db)):
    # Placeholder data for the new dashboard sections
    import random
    # S3 로드 데이터에서 샘플링
    sample = lambda n: random.sample(clothing_data, min(n, len(clothing_data))) if clothing_data else []
    viewed_products = sample(6)
    recommended_products = sample(6)
    jjim_products = []
    
    # Debugging: Print image URLs to console
    print("--- Viewed Products Image URLs ---")
    for p in viewed_products:
        print(p.get('사진') or p.get('대표이미지URL', 'No Image URL'))
    print("--- Recommended Products Image URLs ---")
    for p in recommended_products:
        print(p.get('사진') or p.get('대표이미지URL', 'No Image URL'))
    print("--- Jjim Products Image URLs ---")
    for p in jjim_products:
        print(p.get('사진') or p.get('대표이미지URL', 'No Image URL'))

    # 내 찜목록 불러오기 (전체 데이터에서 사용자 찜만 필터)
    user = get_user_by_username(db, request.session.get("user_name"))
    ids = list_jjim_product_ids(db, user.id) if user else []

    id_set = set(str(pid) for pid in ids)
    jjim_products = [p for p in clothing_data if str(p.get('상품ID')) in id_set]

    return templates.TemplateResponse("mypage/mypage.html", {
        "request": request,
        "viewed_products": viewed_products,
        "recommended_products": recommended_products,
        "jjim_products": jjim_products
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