from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/recommend-page")
def recommend_page(request: Request):
    return templates.TemplateResponse("recommend.html", {"request": request, "title": "추천"})