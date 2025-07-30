from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/faq-page")
def faq_page(request: Request):
    return templates.TemplateResponse("faq.html", {"request": request, "title": "FAQ"})
