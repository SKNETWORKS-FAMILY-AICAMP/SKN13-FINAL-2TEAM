from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Corrected imports
from apps.home.router import router as home_router
from apps.auth.router import router as auth_router
from apps.recommend.router import router as recommend_router
from apps.preference.router import router as preference_router
from apps.review.router import router as review_router
from apps.cart.router import router as cart_router
from apps.products.router import router as products_router
from apps.survey.router import router as survey_router
from apps.faq.router import router as faq_router
from apps.mypage.router import router as mypage_router

from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import os
from apps.auth.oauth.google_oauth import router as google_oauth_router  # Google OAuth 라우터
from apps.auth.oauth.kakao_oauth import router as kakao_oauth_router # Kakao OAuth 라우터

app = FastAPI()

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
app.include_router(review_router, prefix="/review", tags=["Review"])
app.include_router(cart_router, prefix="/cart", tags=["Cart"])
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(survey_router, prefix="/survey", tags=["Survey"])
app.include_router(faq_router, prefix="/faq", tags=["FAQ"])
app.include_router(mypage_router, prefix="/mypage", tags=["MyPage"])