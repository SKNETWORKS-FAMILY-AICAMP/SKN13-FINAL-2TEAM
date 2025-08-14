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
    """
    메인 홈페이지를 렌더링합니다.
    서버 시작 시 미리 로드된 clothing_data를 사용합니다.
    """
    # 데이터가 비어있는 경우를 대비하여 안전하게 처리 (불필요한 대량 로그 제거)
    if not clothing_data:
        sampled_data = []
    else:
        # 표시할 데이터 수를 100개 또는 전체 데이터 수 중 작은 값으로 제한
        count = min(100, len(clothing_data))
        sampled_data = random.sample(clothing_data, count)

    # 데이터를 4개의 섹션으로 분할
    section_size = len(sampled_data) // 4
    sections = {
        f"section{i+1}_items": sampled_data[i*section_size : (i+1)*section_size]
        for i in range(4)
    }

    return templates.TemplateResponse(
        "home.html", 
        {"request": request, **sections}
    )
