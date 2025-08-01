from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.routing import APIRoute
from passlib.context import CryptContext

router = APIRouter()
templates = Jinja2Templates(directory="templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 임시 사용자 저장소 (서버 재시작 시 데이터 초기화)
users = {}

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
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = users.get(username)
    if not user or not pwd_context.verify(password, user["hashed_password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다."})
    
    request.session["user_name"] = username
    return RedirectResponse(url="/mypage/", status_code=status.HTTP_302_FOUND)

@router.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup", response_class=HTMLResponse)
async def signup_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in users:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "이미 존재하는 아이디입니다."})
    
    hashed_password = pwd_context.hash(password)
    users[username] = {"username": username, "hashed_password": hashed_password}
    
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
