from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter()

# OAuth 객체 등록
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)
# 1. 구글 로그인 시작
@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")  # 예: http://localhost:8000/auth/google/callback
    return await oauth.google.authorize_redirect(request, redirect_uri)

# 2. 구글 콜백 처리
@router.get("/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = await oauth.google.userinfo(token=token)  # ✅ 핵심 변경
        request.session['user'] = dict(user)
        return RedirectResponse(url="/")
    except Exception as e:
        print("❗ OAuth Error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

# 3. 로그아웃
@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="http://127.0.0.1:8000/")
