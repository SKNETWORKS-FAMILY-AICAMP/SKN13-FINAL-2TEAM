from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

app = FastAPI()

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
app.include_router(home_router, tags=["Home"])
app.include_router(auth_router, tags=["Auth"])
app.include_router(preference_router, tags=["Preference"])
app.include_router(jjim_router, tags=["Jjim"])
app.include_router(faq_router, tags=["FAQ"])
app.include_router(mypage_router, tags=["Mypage"])
app.include_router(products_router, tags=["Products"])
app.include_router(survey_router, tags=["Survey"])
app.include_router(chatbot_router, tags=["Chatbot"])
app.include_router(chatbot_debug_router, tags=["Chatbot Debug"])

# 404 에러 핸들러
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return await http_exception_handler(request, exc)

# 애플리케이션 시작 시 챗봇 데이터 초기화
@app.on_event("startup")
async def startup_event():
    from routers.router_chatbot import initialize_chatbot_data
    initialize_chatbot_data()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)