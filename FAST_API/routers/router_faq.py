from fastapi import APIRouter, Request, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Sample FAQ data
faq_data = [
    {
        "question": "Q: 이 웹사이트는 무엇을 하는 곳인가요?",
        "answer": "A: 저희 웹사이트는 사용자의 취향에 맞는 의류를 추천해주는 서비스입니다."
    },
    {
        "question": "Q: 추천 시스템은 어떻게 작동하나요?",
        "answer": "A: 사용자가 응답한 설문조사 결과를 바탕으로 머신러닝 모델이 개인화된 의류를 추천합니다."
    },
    {
        "question": "Q: 회원가입은 어떻게 하나요?",
        "answer": "A: 홈페이지 상단의 ‘회원가입’ 버튼을 클릭하여 간단한 정보를 입력하면 가입이 완료됩니다."
    },
    {
        "question": "Q: 추천받은 의류는 어디서 구매할 수 있나요?",
        "answer": "A: 현재는 추천 서비스만 제공하고 있으며, 구매 기능은 준비 중에 있습니다."
    }
]

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def faq(request: Request):
    return templates.TemplateResponse("faq.html", {"request": request, "faq_data": faq_data})