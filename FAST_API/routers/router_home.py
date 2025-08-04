from fastapi import APIRouter, Request, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import get_random_products

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def read_home(request: Request):
    # 데이터셋에서 100개의 아이템을 무작위로 선택
    sampled_data = get_random_products(100)

    # 데이터를 4개의 섹션으로 나눕니다.
    section1_data = sampled_data[0:25]
    section2_data = sampled_data[25:50]
    section3_data = sampled_data[50:75]
    section4_data = sampled_data[75:100]

    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request,
            "section1_items": section1_data,
            "section2_items": section2_data,
            "section3_items": section3_data,
            "section4_items": section4_data
        }
    )
