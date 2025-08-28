from fastapi import APIRouter, Request, Depends, HTTPException, status
from dependencies import login_required
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from db import get_db
from crud.user_crud import get_user_by_username, upsert_user_preference
from schemas.schemas_survey import SurveyAnswers # 새로운 스키마를 임포트

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- 점수표 정의 ---
scoring_map = {
    'q1_priority': {
        'comfort': {'Casual': 2},
        'trend': {'Street': 2},
        'neat': {'Formal': 2},
        'personality': {'Street': 1, 'Minimal': 1}
    },
    'q2_daily_look': {
        'casual_look': {'Casual': 2},
        'office_look': {'Formal': 2},
        'street_fashion': {'Street': 2},
        'minimal_mono': {'Minimal': 2}
    },
    'q3_fit': {
        'loose': {'Street': 2, 'Casual': 1},
        'regular': {'Casual': 1, 'Formal': 1},
        'slim': {'Minimal': 2, 'Formal': 1},
        'tpo': {'Casual': 1, 'Formal': 1, 'Street': 1, 'Minimal': 1}
    },
    'q4_color': {
        'vivid': {'Street': 2},
        'pastel': {'Casual': 1, 'Formal': 1},
        'neutral': {'Minimal': 2},
        'mono': {'Minimal': 2, 'Formal': 1}
    },
    'q5_direction': {
        'latest_style': {'Street': 1},
        'multi_purpose': {'Formal': 1, 'Casual': 1},
        'unique_style': {'Street': 2},
        'safe_style': {'Minimal': 1, 'Formal': 1}
    }
}

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def survey_page(request: Request):
    return templates.TemplateResponse("survey/survey.html", {"request": request})

@router.post("/", response_class=RedirectResponse)
async def submit_survey(
    answers: SurveyAnswers,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    user = get_user_by_username(db, user_name)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    scores = {'Casual': 0, 'Street': 0, 'Formal': 0, 'Minimal': 0}
    
    # 답변을 dict로 변환하여 None 값 제외
    user_answers = answers.dict(exclude_none=True)

    # 점수 계산
    for question, answer_key in user_answers.items():
        if question in scoring_map and answer_key in scoring_map[question]:
            for style, points in scoring_map[question][answer_key].items():
                if style in scores:
                    scores[style] += points

    # 최고점 스타일 찾기
    if not scores or all(s == 0 for s in scores.values()):
        # 모든 점수가 0이면 기본값 설정 또는 오류 처리
        preferred_style_str = "Casual" # 기본값
    else:
        preferred_style_str = max(scores, key=scores.get)

    # 데이터베이스에 최종 결과 저장
    upsert_user_preference(
        db=db,
        user_id=user.id,
        preferred_style=preferred_style_str,
        survey_completed=True
    )

    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@router.post("/decline", response_class=JSONResponse)
async def decline_survey(
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    user = get_user_by_username(db, user_name)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    upsert_user_preference(
        db=db,
        user_id=user.id,
        survey_completed=True
    )

    return {"message": "Survey declined and status updated."}