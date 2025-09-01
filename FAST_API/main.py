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
from starlette.middleware.cors import CORSMiddleware
from db import init_db, bootstrap_admin
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

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
from routers.router_cache_admin import router as cache_admin_router
from routers.oauth.google_oauth import router as google_oauth_router
from routers.oauth.kakao_oauth import router as kakao_oauth_router

app = FastAPI()

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 미들웨어 및 정적 파일 설정
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET", "change-me"),
    max_age=3600,  # 세션 만료 시간 1시간
    same_site="lax",  # CSRF 보호
    https_only=False  # 개발 환경에서는 False, 프로덕션에서는 True
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Jinja2Templates에 url_for 함수 추가
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

def url_for(request: StarletteRequest, name: str, **path_params: str) -> str:
    if name == "static":
        return f"/static/{path_params.get('filename', '')}"
    return request.url_for(name, **path_params)

templates.env.globals["url_for"] = url_for

# 라우터 등록
app.include_router(home_router, tags=["Home"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(preference_router, prefix="/preference", tags=["Preference"])
app.include_router(jjim_router, prefix="/jjim", tags=["Jjim"])
app.include_router(faq_router, prefix="/faq", tags=["FAQ"])
app.include_router(mypage_router, prefix="/mypage", tags=["Mypage"])
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(survey_router, prefix="/survey", tags=["Survey"])
app.include_router(chatbot_router, prefix="/chat", tags=["Chatbot"])
app.include_router(cache_admin_router, prefix="/admin", tags=["Cache Admin"])
app.include_router(google_oauth_router, prefix="/auth", tags=["oauth-google"])
app.include_router(kakao_oauth_router, prefix="/auth", tags=["oauth-kakao"])

# 404 에러 핸들러
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return await http_exception_handler(request, exc)

# 애플리케이션 시작 시 데이터 초기화
@app.on_event("startup")
async def startup_event():
    # DB 테이블 생성
    init_db()
    bootstrap_admin()

    # S3에서 제품 데이터 로드
    from s3_data_loader import get_product_data_from_s3
    from data_store import clothing_data, processed_clothing_data
    from routers.router_products import process_product_data

    s3_file_key = os.getenv("S3_FILE_KEY", "product_info.csv")

    print("🚀 애플리케이션 시작: S3 데이터 로드를 시작합니다...")
    loaded_data = get_product_data_from_s3(s3_file_key)
    if loaded_data:
        clothing_data.extend(loaded_data)
        print(f"✅ S3 데이터 로드 완료: {len(clothing_data)}개 상품")

        # 데이터 사전 처리 및 캐싱
        print("🔄 상품 데이터 사전 처리를 시작합니다...")
        processed_data = process_product_data(clothing_data)
        processed_clothing_data.extend(processed_data)
        print(f"✅ 상품 데이터 사전 처리 및 캐싱 완료: {len(processed_clothing_data)}개 상품")
    else:
        print("⚠️ S3에서 데이터를 불러오지 못했거나 데이터가 비어있습니다.")

    print("✅ 챗봇 데이터는 기본 clothing_data를 사용합니다")

if __name__ == "__main__":
    import uvicorn
    import os

    workers = int(os.getenv("UVICORN_WORKERS", "2"))
    print(f"워커 수: {workers}")

    ssl_cert_file = os.getenv("FASTAPI_SSL_CERT_FILE")
    ssl_key_file = os.getenv("FASTAPI_SSL_KEY_FILE")

    if ssl_cert_file and ssl_key_file and os.path.exists(ssl_cert_file) and os.path.exists(ssl_key_file):
        uvicorn.run(
            "main:app",  # app → "main:app"으로 변경
            host="0.0.0.0",
            port=443,
            ssl_certfile=ssl_cert_file,
            ssl_keyfile=ssl_key_file,
            workers=workers  # 이 줄 추가
        )
    else:
            uvicorn.run(
            "main:app",  # app → "main:app"으로 변경
            host="0.0.0.0",
            port=8000,
            workers=workers  # 이 줄 추가
        )


from sqlalchemy.orm import Session
from db import get_db
from crud.faq_crud import create_faq
from models.models_faq import FAQ

app = FastAPI()

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 미들웨어 및 정적 파일 설정
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-me"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Jinja2Templates에 url_for 함수 추가
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

def url_for(request: StarletteRequest, name: str, **path_params: str) -> str:
    if name == "static":
        return f"/static/{path_params.get('filename', '')}"
    return request.url_for(name, **path_params)

templates.env.globals["url_for"] = url_for

# 라우터 등록
app.include_router(home_router, tags=["Home"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(preference_router, prefix="/preference", tags=["Preference"])
app.include_router(jjim_router, prefix="/jjim", tags=["Jjim"])
app.include_router(faq_router, prefix="/faq", tags=["FAQ"])
app.include_router(mypage_router, prefix="/mypage", tags=["Mypage"])
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(survey_router, prefix="/survey", tags=["Survey"])
app.include_router(chatbot_router, prefix="/chat", tags=["Chatbot"])
app.include_router(cache_admin_router, prefix="/admin", tags=["Cache Admin"])
app.include_router(google_oauth_router, prefix="/auth", tags=["oauth-google"])
app.include_router(kakao_oauth_router, prefix="/auth", tags=["oauth-kakao"])

# 404 에러 핸들러
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return await http_exception_handler(request, exc)

# 애플리케이션 시작 시 데이터 초기화
@app.on_event("startup")
async def startup_event():
    # DB 테이블 생성
    init_db()
    bootstrap_admin()

    # FAQ 데이터 초기화 (테이블이 비어있을 경우에만)
    db_session = next(get_db()) # Get a session
    if db_session.query(FAQ).count() == 0:
        initial_faq_data = [
            {"id": "q-about", "category": "general", "question": "이 사이트는 어떤 서비스인가요?", "answer": "Ivle Malle은 취향/체형/계절컬러를 반영해 코디를 추천하는 AI 서비스입니다."},
            {"id": "q-accuracy", "category": "recommendation", "question": "추천 정확도는 어떻게 높여요?", "answer": "스타일 설문 완료, 하트/저장/클릭 이력, 계절 및 트렌드 반영으로 지속 개선됩니다."},
            {"id": "q-signup", "category": "account", "question": "회원가입 없이 사용할 수 있나요?", "answer": "둘러보기는 가능하지만, 개인화 추천/즐겨찾기/히스토리는 회원에게 제공됩니다."},
            {"id": "q-payment", "category": "order", "question": "지원 결제 수단은 무엇인가요?", "answer": "신용/체크카드 및 주요 간편결제를 지원합니다. 국가/은행 정책에 따라 일부 제한될 수 있어요."},
            {"id": "q-return", "category": "returns", "question": "반품/환불은 어떻게 진행하나요?", "answer": "주문 내역에서 반품 신청 → 수거 → 검수 후 환불 처리됩니다. 자세한 정책은 반품 안내를 확인하세요."},
            {"id": "q-privacy", "category": "privacy", "question": "개인정보는 어떻게 사용되나요?", "answer": "추천 품질 향상을 위한 최소한의 데이터만 수집하며, 개인정보 처리방침을 준수합니다."},
            {"id": "q-signup-process", "category": "account", "question": "회원가입은 어떻게 하나요?", "answer": "홈페이지 우측 상단의 '회원가입' 버튼을 클릭하거나, Google/Kakao 계정으로 간편하게 가입할 수 있습니다."},
            {"id": "q-survey-purpose", "category": "recommendation", "question": "스타일 설문은 왜 해야 하나요?", "answer": "스타일 설문은 고객님의 취향과 체형을 파악하여 더욱 정확하고 개인화된 의류를 추천해 드리기 위함입니다."},
            {"id": "q-chatbot-usage", "category": "general", "question": "챗봇은 어떻게 이용하나요?", "answer": "화면 우측 하단의 챗봇 아이콘을 클릭하여 챗봇과 대화할 수 있습니다. 코디 추천이나 궁금한 점을 물어보세요."},
            {"id": "q-jjim-location", "category": "account", "question": "찜 목록은 어디서 확인하나요?", "answer": "로그인 후 마이페이지에서 '찜 목록' 메뉴를 통해 확인하실 수 있습니다."}
        ]
        for faq_item in initial_faq_data:
                        create_faq(db_session, question=faq_item["question"], answer=faq_item["answer"])
        db_session.close()
        print("✅ FAQ 데이터 초기화 완료")
    else:
        print("ℹ️ FAQ 테이블에 데이터가 이미 존재합니다. 초기화를 건너뜁니다.")

    # S3에서 제품 데이터 로드
    from s3_data_loader import get_product_data_from_s3
    from data_store import clothing_data, processed_clothing_data
    from routers.router_products import process_product_data

    s3_file_key = os.getenv("S3_FILE_KEY", "product_info.csv")

    print("🚀 애플리케이션 시작: S3 데이터 로드를 시작합니다...")
    loaded_data = get_product_data_from_s3(s3_file_key)
    if loaded_data:
        clothing_data.extend(loaded_data)
        print(f"✅ S3 데이터 로드 완료: {len(clothing_data)}개 상품")

        # 데이터 사전 처리 및 캐싱
        print("🔄 상품 데이터 사전 처리를 시작합니다...")
        processed_data = process_product_data(clothing_data)
        processed_clothing_data.extend(processed_data)
        print(f"✅ 상품 데이터 사전 처리 및 캐싱 완료: {len(processed_clothing_data)}개 상품")
    else:
        print("⚠️ S3에서 데이터를 불러오지 못했거나 데이터가 비어있습니다.")

    print("✅ 챗봇 데이터는 기본 clothing_data를 사용합니다")

if __name__ == "__main__":
    import uvicorn
    import os

    workers = int(os.getenv("UVICORN_WORKERS", "2"))
    print(f"워커 수: {workers}")

    ssl_cert_file = os.getenv("FASTAPI_SSL_CERT_FILE")
    ssl_key_file = os.getenv("FASTAPI_SSL_KEY_FILE")

    if ssl_cert_file and ssl_key_file and os.path.exists(ssl_cert_file) and os.path.exists(ssl_key_file):
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=443,
            ssl_certfile=ssl_cert_file,
            ssl_keyfile=ssl_key_file,
            workers=workers
        )
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            workers=workers
        )
