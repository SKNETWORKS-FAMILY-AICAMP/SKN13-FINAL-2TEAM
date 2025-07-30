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
async def read_home(request: Request):
    # 데이터셋에서 100개의 아이템을 무작위로 선택
    if len(clothing_data) > 100:
        sampled_data = random.sample(clothing_data, 100)
    else:
        sampled_data = clothing_data

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
