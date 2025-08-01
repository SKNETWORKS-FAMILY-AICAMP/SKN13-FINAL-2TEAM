# routers/oauth/google_oauth.py

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter()

# Google OAuth 등록
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = await oauth.google.userinfo(token=token)  # 안정적인 방식
        request.session['user'] = dict(user)
        return RedirectResponse(url="/")
    except Exception as e:
        print("Google OAuth Error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
