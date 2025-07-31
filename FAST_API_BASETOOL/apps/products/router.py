import csv
import random
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def products(request: Request):
    products_data = []
    with open('products.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            products_data.append(row)
    
    random_products = random.sample(products_data, min(10, len(products_data)))

    return templates.TemplateResponse("products/category_browse.html", {"request": request, "products": random_products})