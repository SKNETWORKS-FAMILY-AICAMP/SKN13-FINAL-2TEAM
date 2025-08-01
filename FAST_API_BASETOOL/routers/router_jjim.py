from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import get_all_products, get_random_products
import urllib.parse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def jjim_list(request: Request):
    # Select 4 random products for the jjim list
    random_jjim_products = get_random_products(4)
    return templates.TemplateResponse("jjim/jjim.html", {"request": request, "jjim_products": random_jjim_products})

@router.get("/compare/{product_names}", response_class=HTMLResponse)
async def compare_products(request: Request, product_names: str):
    all_products = get_all_products()
    decoded_product_names = urllib.parse.unquote(product_names)
    selected_names = [name.strip() for name in decoded_product_names.split(',')]
    products_to_compare = []

    for name in selected_names:
        found_product = next((p for p in all_products if p.get('상품명') == name), None)
        if found_product:
            products_to_compare.append(found_product)

    if not products_to_compare:
        raise HTTPException(status_code=404, detail="Products not found for comparison")

    return templates.TemplateResponse("jjim/compare.html", {"request": request, "products": products_to_compare})