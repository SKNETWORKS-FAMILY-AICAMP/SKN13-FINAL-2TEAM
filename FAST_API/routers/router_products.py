from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import get_random_products

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def products(request: Request):
    random_products = get_random_products(10)
    return templates.TemplateResponse("products/category_browse.html", {"request": request, "products": random_products})