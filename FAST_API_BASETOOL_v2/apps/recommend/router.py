from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import random

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# CSV 파일에서 데이터 읽기
df = pd.read_csv("products.csv")

# "대표이미지URL" 열의 값을 수정하여 "https://" 추가
df["대표이미지URL"] = "https:" + df["대표이미지URL"]

# 데이터프레임을 딕셔너리 리스트로 변환
clothing_data = df.to_dict("records")

@router.get("/", response_class=HTMLResponse)
async def recommend(request: Request):
    return templates.TemplateResponse("recommend.html", {"request": request})

@router.get("/taste", response_class=HTMLResponse)
async def taste_recommend(request: Request):
    # 데이터셋에서 10개의 아이템을 무작위로 선택
    if len(clothing_data) > 20:
        recommended_items = random.sample(clothing_data, 20)
    else:
        recommended_items = clothing_data

    return templates.TemplateResponse(
        "taste_recommend.html", 
        {
            "request": request,
            "recommended_items": recommended_items
        }
    )
