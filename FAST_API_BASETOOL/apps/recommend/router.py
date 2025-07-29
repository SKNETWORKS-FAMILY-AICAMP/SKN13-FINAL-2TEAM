from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def recommend(request: Request):
    return templates.TemplateResponse("recommend.html", {"request": request})

@router.get("/taste", response_class=HTMLResponse)
async def taste_recommend(request: Request):
    return templates.TemplateResponse("taste_recommend.html", {"request": request})