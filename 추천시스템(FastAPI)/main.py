from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 라우터 불러오기
from app.user.router import router as user_router
from app.product.router import router as product_router
from app.recommend.router import router as recommend_router

app = FastAPI()

# 정적 파일과 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
app.include_router(user_router, prefix="/users")
app.include_router(product_router, prefix="/products")
app.include_router(recommend_router, prefix="/recommend")

# 홈 페이지 라우팅
@app.get("/")
def get_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "FastAPI 프로젝트 시작"})
