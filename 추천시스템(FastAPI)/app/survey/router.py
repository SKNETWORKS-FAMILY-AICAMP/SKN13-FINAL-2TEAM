from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/survey-page")
def survey_page(request: Request):
    return templates.TemplateResponse("survey.html", {"request": request, "title": "설문조사"})