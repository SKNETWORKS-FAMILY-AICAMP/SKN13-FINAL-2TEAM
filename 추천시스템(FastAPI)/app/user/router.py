from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 회원가입 페이지
@router.get("/users/register")
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "title": "회원가입"})

# 로그인 페이지
@router.get("/users/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "로그인"})

# 회원가입 처리
@router.post("/users/register")
def register_user(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    print(f"[회원가입] 사용자: {username}, 이메일: {email}, 비밀번호: {password}")
    return RedirectResponse(url="/", status_code=302)

# 로그인 처리
@router.post("/users/login")
def login_user(username: str = Form(...), password: str = Form(...)):
    print(f"[로그인 시도] 사용자: {username}, 비밀번호: {password}")
    return RedirectResponse(url="/", status_code=302)
