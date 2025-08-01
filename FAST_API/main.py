from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
import database  # 데이터베이스 모듈 임포트

# Corrected imports
from routers.router_home import router as home_router
from routers.router_auth import router as auth_router
from routers.router_recommend import router as recommend_router
from routers.router_preference import router as preference_router
from routers.router_jjim import router as jjim_router
from routers.router_products import router as products_router
from routers.router_survey import router as survey_router
from routers.router_faq import router as faq_router
from routers.router_mypage import router as mypage_router

from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import os
from routers.oauth.google_oauth import router as google_oauth_router  # Google OAuth 라우터
from routers.oauth.kakao_oauth import router as kakao_oauth_router # Kakao OAuth 라우터

app = FastAPI()

templates = Jinja2Templates(directory="templates")

load_dotenv()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
# Note: The home router does not have a prefix, so it handles the root path "/".
app.include_router(home_router, tags=["Home"])

# For other routers, the prefix is added. 
# e.g., the /login path in auth/router.py becomes /auth/login
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(google_oauth_router, prefix="/auth", tags=["Google"])
app.include_router(kakao_oauth_router, prefix="/auth", tags=["Kakao"])
app.include_router(recommend_router, prefix="/recommend", tags=["Recommendation"])
app.include_router(preference_router, prefix="/preference", tags=["Preference"]) 
app.include_router(jjim_router, prefix="/jjim", tags=["Jjim"])
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(survey_router, prefix="/survey", tags=["Survey"])
app.include_router(faq_router, prefix="/faq", tags=["FAQ"])
app.include_router(mypage_router, prefix="/mypage", tags=["MyPage"])

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return await http_exception_handler(request, exc)