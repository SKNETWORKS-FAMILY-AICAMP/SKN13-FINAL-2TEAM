from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import get_random_products

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def preference(request: Request):
    items = get_random_products(20)
    return templates.TemplateResponse(
        "preference/preference.html", 
        {"request": request, "recommended_items": items}
    )