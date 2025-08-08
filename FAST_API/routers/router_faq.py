from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dependencies import login_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- Dynamic FAQ data (id, category, question, answer) ---
faq_data = [
    {"id": "q-about", "category": "general", "question": "이 사이트는 어떤 서비스인가요?", "answer": "Ivle Malle은 취향/체형/계절컬러를 반영해 코디를 추천하는 AI 서비스입니다."},
    {"id": "q-accuracy", "category": "recommendation", "question": "추천 정확도는 어떻게 높여요?", "answer": "스타일 설문 완료, 하트/저장/클릭 이력, 계절 및 트렌드 반영으로 지속 개선됩니다."},
    {"id": "q-signup", "category": "account", "question": "회원가입 없이 사용할 수 있나요?", "answer": "둘러보기는 가능하지만, 개인화 추천/즐겨찾기/히스토리는 회원에게 제공됩니다."},
    {"id": "q-payment", "category": "order", "question": "지원 결제 수단은 무엇인가요?", "answer": "신용/체크카드 및 주요 간편결제를 지원합니다. 국가/은행 정책에 따라 일부 제한될 수 있어요."},
    {"id": "q-return", "category": "returns", "question": "반품/환불은 어떻게 진행하나요?", "answer": "주문 내역에서 반품 신청 → 수거 → 검수 후 환불 처리됩니다. 자세한 정책은 반품 안내를 확인하세요."},
    {"id": "q-privacy", "category": "privacy", "question": "개인정보는 어떻게 사용되나요?", "answer": "추천 품질 향상을 위한 최소한의 데이터만 수집하며, 개인정보 처리방침을 준수합니다."}
]

categories = [
    {"key": "all", "label": "전체"},
    {"key": "general", "label": "일반"},
    {"key": "account", "label": "계정"},
    {"key": "recommendation", "label": "추천"},
    {"key": "order", "label": "주문/결제"},
    {"key": "returns", "label": "반품/환불"},
    {"key": "privacy", "label": "개인정보"},
]

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def faq(request: Request):
    return templates.TemplateResponse("faq.html", {"request": request, "faq_data": faq_data, "categories": categories})