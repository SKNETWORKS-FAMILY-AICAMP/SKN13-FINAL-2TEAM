from dotenv import load_dotenv

# 환경변수 로드 (가장 먼저 실행)
load_dotenv()

import sys
import os

# 프로젝트 루트 경로를 시스템 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
# Database imports removed - not needed when database is disabled
# from db import init_db, bootstrap_admin

# 라우터 임포트
from routers.router_home import router as home_router
from routers.router_auth import router as auth_router
from routers.router_preference import router as preference_router
from routers.router_jjim import router as jjim_router
from routers.router_faq import router as faq_router
from routers.router_mypage import router as mypage_router
from routers.router_products import router as products_router
from routers.router_survey import router as survey_router
from routers.router_chatbot import router as chatbot_router
from routers.router_chatbot_debug import router as chatbot_debug_router
from routers.router_cache_admin import router as cache_admin_router

app = FastAPI()

# 미들웨어 및 정적 파일 설정
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-me"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
# Note: The home router does not have a prefix, so it handles the root path "/".
app.include_router(home_router, tags=["Home"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(preference_router, prefix="/preference", tags=["Preference"])
app.include_router(jjim_router, prefix="/jjim", tags=["Jjim"])
app.include_router(faq_router, prefix="/faq", tags=["FAQ"])
app.include_router(mypage_router, prefix="/mypage", tags=["Mypage"])
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(survey_router, prefix="/survey", tags=["Survey"])
app.include_router(chatbot_router, prefix="/chat", tags=["Chatbot"])
app.include_router(chatbot_debug_router, prefix="/chat-debug", tags=["Chatbot Debug"])
app.include_router(cache_admin_router, prefix="/admin", tags=["Cache Admin"])

# 404 에러 핸들러
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return await http_exception_handler(request, exc)

# 애플리케이션 시작 시 데이터 초기화
@app.on_event("startup")
async def startup_event():
    # DB 테이블 생성 - TEMPORARILY DISABLED due to connection issues
    # init_db()
    # bootstrap_admin()

    # S3에서 제품 데이터 로드 및 캐싱
    from s3_data_loader import get_product_data_from_s3
    from data_store import clothing_data
    
    # .env 파일에서 S3 파일 키를 가져옵니다.
    s3_file_key = os.getenv("S3_FILE_KEY", "path/to/your/default/file.csv")
    
    print("🚀 애플리케이션 시작: S3 데이터 로드를 시작합니다...")
    loaded_data = get_product_data_from_s3(s3_file_key)
    if loaded_data:
        clothing_data.extend(loaded_data)
        print(f"✅ S3 데이터 로드 및 전역 데이터 저장소 초기화 완료: {len(clothing_data)}개 상품")
    else:
        print("⚠️ S3에서 데이터를 불러오지 못했거나 데이터가 비어있습니다.")

    # 챗봇 데이터 초기화
    from routers.router_chatbot import initialize_chatbot_data
    print("🤖 챗봇 데이터 초기화를 시작합니다...")
    initialize_chatbot_data()
    print("✅ 챗봇 데이터 초기화 완료")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)