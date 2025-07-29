from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 설문조사 데이터 모델 정의
class SurveyData(BaseModel):
    styles: List[str]

@router.get("/", response_class=HTMLResponse)
async def survey(request: Request):
    return templates.TemplateResponse("survey.html", {"request": request})

@router.post("/", response_class=JSONResponse)
async def submit_survey(survey_data: SurveyData):
    print("Received survey data:", survey_data.styles)
    # 여기에 설문조사 데이터를 처리하는 로직을 추가합니다.
    # 예: 데이터베이스에 저장, 사용자 취향 분석 등
    return {"message": "Survey data received successfully!", "selected_styles": survey_data.styles}
