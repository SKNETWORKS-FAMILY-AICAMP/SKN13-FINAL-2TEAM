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
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다."})
    
    request.session["user_name"] = user.username
    request.session["role"] = user.role or "user"
    return RedirectResponse(url="/mypage/", status_code=status.HTTP_302_FOUND)

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
    preferred_color: str = Form(None),
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
    user = User(username=username, hashed_password=hash_password(password), email=email, gender=gender, role="user")
    db.add(user)
    db.commit()
    db.refresh(user)

    # 선호정보 저장
    upsert_user_preference(
        db,
        user_id=user.id,
        height=height,
        weight=weight,
        preferred_color=preferred_color,
        preferred_style=None,
    )

    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
