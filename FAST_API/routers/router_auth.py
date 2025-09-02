import uuid
from typing import List, Optional

from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db import get_db
from models.models_auth import User
from crud.user_crud import (
    get_user_by_username,
    get_user_by_email,
    create_user,
    upsert_user_preference,
    get_preference_by_user_id
)
from security import hash_password, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class LoginForm:
    def __init__(self, request: Request):
        self.request: Request = request
        self.username: str = ""
        self.password: str = ""

    async def create_oauth2_form(self):
        form = await self.request.form()
        self.username = form.get("username")
        self.password = form.get("password")


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다."})
    
    # 기존 세션 데이터 삭제 후 새로운 세션 생성
    request.session.clear()
    
    # 새로운 세션에 사용자 정보 저장
    request.session["user_name"] = user.username
    request.session["user_id"] = user.id
    request.session["role"] = user.role or "user"
    request.session["login_time"] = str(uuid.uuid4())  # 고유한 로그인 식별자
    
    # 관리자인 경우 관리자 페이지로, 일반 사용자인 경우 홈으로 리다이렉션
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@router.get("/logout")
async def logout(request: Request):
    # 세션 데이터 완전 삭제
    request.session.clear()
    
    # 새로운 세션 ID 생성 (세션 무효화)
    # FastAPI SessionMiddleware는 자동으로 새로운 세션을 생성합니다
    # 하지만 명시적으로 세션을 재생성하기 위해 세션 ID를 변경
    request.session["_new_session"] = True
    
    # 로그아웃 페이지로 리다이렉트 (챗봇 세션 초기화를 위해)
    return RedirectResponse(url="/auth/logout-page", status_code=status.HTTP_302_FOUND)

@router.get("/logout-page", response_class=HTMLResponse)
async def logout_page(request: Request):
    return templates.TemplateResponse("logout.html", {"request": request})

@router.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup", response_class=HTMLResponse)
async def signup_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    gender: str = Form(None),
    height: int = Form(None),
    weight: int = Form(None),
    preferred_color: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
):
    # 비밀번호 정책 검사 (최소 8자, 대문자/소문자/숫자 포함)
    import re
    pw = password or ""
    if len(pw) < 8 or not re.search(r"[A-Z]", pw) or not re.search(r"[a-z]", pw) or not re.search(r"\d", pw):
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "비밀번호는 8자 이상이며 대문자, 소문자, 숫자를 모두 포함해야 합니다."},
        )

    # 중복 검사: 아이디/이메일
    if get_user_by_username(db, username):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "이미 존재하는 아이디입니다."})
    if get_user_by_email(db, email):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "이미 존재하는 이메일입니다."})

    # 사용자 생성
    user = User(username=username, password=hash_password(password), email=email, gender=gender, role="user")
    db.add(user)
    db.commit()
    db.refresh(user)

    # 선호정보 저장 (색상 리스트를 문자열로 변환)
    preferred_color_str = ",".join(preferred_color) if preferred_color else None
    upsert_user_preference(
        db=db,
        user_id=user.id,
        height=height,
        weight=weight,
        preferred_color=preferred_color_str,
        preferred_style=None,
        survey_completed=False  # survey_completed 값을 False로 명시적으로 전달
    )

    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
