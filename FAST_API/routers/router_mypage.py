from fastapi import APIRouter, Request, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import get_random_products

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def mypage(request: Request):
    # Placeholder data for the new dashboard sections
    viewed_products = get_random_products(6)      # 최근 본 상품
    recommended_products = get_random_products(6) # 추천 상품
    jjim_products = get_random_products(6)        # 찜한 상품
    
    # Debugging: Print image URLs to console
    print("--- Viewed Products Image URLs ---")
    for p in viewed_products:
        print(p.get('대표이미지URL', 'No Image URL'))
    print("--- Recommended Products Image URLs ---")
    for p in recommended_products:
        print(p.get('대표이미지URL', 'No Image URL'))
    print("--- Jjim Products Image URLs ---")
    for p in jjim_products:
        print(p.get('대표이미지URL', 'No Image URL'))

    return templates.TemplateResponse("mypage/mypage.html", {
        "request": request,
        "viewed_products": viewed_products,
        "recommended_products": recommended_products,
        "jjim_products": jjim_products
    })