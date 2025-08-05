from fastapi import APIRouter, Request, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from data_store import clothing_data
import random

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def read_home(request: Request):
    # --- 최종 디버깅 코드 ---
    print(f"[최종 디버그] clothing_data의 첫 번째 항목: {clothing_data[0] if clothing_data else '데이터 없음'}")
    
    if clothing_data:
        count = min(100, len(clothing_data))
        sampled_data = random.sample(clothing_data, count)
    else:
        sampled_data = []

    section_size = len(sampled_data) // 4
    section1_data = sampled_data[0:section_size]
    section2_data = sampled_data[section_size:section_size*2]
    section3_data = sampled_data[section_size*2:section_size*3]
    section4_data = sampled_data[section_size*3:]

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
