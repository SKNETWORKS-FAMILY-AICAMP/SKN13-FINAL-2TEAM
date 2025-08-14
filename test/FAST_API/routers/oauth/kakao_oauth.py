# routers/oauth/kakao_oauth.py

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter()

# Kakao OAuth 등록
oauth = OAuth()
oauth.register(
    name='kakao',
    client_id=os.getenv("KAKAO_CLIENT_ID"),
    client_secret=None,  # Kakao는 보통 client_secret 없음
    access_token_url='https://kauth.kakao.com/oauth/token',
    authorize_url='https://kauth.kakao.com/oauth/authorize',
    api_base_url='https://kapi.kakao.com/v2/',
    client_kwargs={'scope': 'profile_nickname profile_image'}
)

@router.get("/kakao/login")
async def kakao_login(request: Request):
    redirect_uri = os.getenv("KAKAO_REDIRECT_URI")
    return await oauth.kakao.authorize_redirect(request, redirect_uri)

@router.get("/kakao/callback")
async def kakao_callback(request: Request):
    try:
        token = await oauth.kakao.authorize_access_token(request)
        resp = await oauth.kakao.get("user/me", token=token)
        profile = resp.json()

        kakao_account = profile.get("kakao_account", {})
        user_info = {
            "id": profile.get("id"),
            "nickname": kakao_account.get("profile", {}).get("nickname"),
            "email": kakao_account.get("email")
        }

        request.session["user"] = user_info
        return RedirectResponse(url="/")
    except Exception as e:
        print("Kakao OAuth Error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
