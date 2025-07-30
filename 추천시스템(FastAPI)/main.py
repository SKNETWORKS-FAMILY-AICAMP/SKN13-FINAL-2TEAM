from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

# 라우터 불러오기
from app.user.router import router as user_router
from app.product.router import router as product_router
from app.recommend.router import router as recommend_router
from app.review.router import router as review_router
from app.survey.router import router as survey_router
from app.faq.router import router as faq_router
from app.chatbot.router import router as chatbot_router

app = FastAPI()

# 정적 파일과 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
app.include_router(user_router)
app.include_router(product_router)
app.include_router(recommend_router)
app.include_router(review_router)
app.include_router(survey_router)
app.include_router(faq_router)
app.include_router(chatbot_router)

# 홈 페이지 라우팅
@app.get("/")
def get_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "FastAPI 프로젝트 시작"})

# 추천 페이지
@app.get("/recommend-page")
def recommend_page(request: Request):
    return templates.TemplateResponse("recommend.html", {"request": request, "title": "상품 추천"})

# 유저 페이지
@app.get("/user-page")
def user_page(request: Request):
    return templates.TemplateResponse("user.html", {"request": request, "title": "유저 페이지"})

@app.get("/chatbot-page")
def show_chatbot(request: Request):
    return templates.TemplateResponse("chatbot.html", {"request": request, "title": "챗봇"})

@app.get("/survey-page")
def show_survey(request: Request):
    return templates.TemplateResponse("survey.html", {"request": request, "title": "설문조사"})

@app.get("/faq-page")
def show_faq(request: Request):
    return templates.TemplateResponse("faq.html", {"request": request, "title": "FAQ"})

# 회원가입 페이지
@app.get("/users/register")
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "title": "회원가입"})

# 로그인 페이지
@app.get("/users/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "로그인"})

# 회원가입 처리
@app.post("/users/register")
def register_user(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    print(f"[회원가입] 사용자: {username}, 이메일: {email}, 비밀번호: {password}")
    return RedirectResponse(url="/", status_code=302)

# 로그인 처리
@app.post("/users/login")
def login_user(username: str = Form(...), password: str = Form(...)):
    print(f"[로그인 시도] 사용자: {username}, 비밀번호: {password}")
    return RedirectResponse(url="/", status_code=302)