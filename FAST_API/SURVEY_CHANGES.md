# 설문조사 페이지 변경 사항 (선호 스타일 저장)

## 문제점
기존 설문조사 페이지(`http://127.0.0.1:8000/survey/`)에서 사용자가 선호 스타일을 선택하여 제출하더라도, 해당 정보가 데이터베이스에 저장되지 않는 문제가 있었습니다. 프론트엔드에서는 스타일 데이터를 백엔드로 전송하고 있었으나, 백엔드에서 이를 처리하고 영구적으로 저장하는 로직이 누락되어 있었습니다.

## 해결책

이 문제를 해결하기 위해 다음 파일들을 수정하거나 새로 생성했습니다.

### 1. `schemas/schemas_survey.py` (새로 생성)
설문조사 데이터의 유효성 검사를 위한 Pydantic 스키마 `SurveyCreate`를 정의했습니다.
```python
from typing import List
from pydantic import BaseModel

class SurveyCreate(BaseModel):
    styles: List[str]
```
이 스키마는 프론트엔드에서 전송하는 `styles` (문자열 리스트) 데이터를 정확히 매핑하여 백엔드에서 유효성을 검사하고 사용할 수 있도록 합니다.

### 2. `models/models_preference.py` (새로 생성/수정)
사용자 선호도 정보를 데이터베이스에 저장하기 위한 SQLAlchemy 모델 `UserPreference`를 정의했습니다. 이 모델은 `users` 테이블의 `User` 모델과 일대일 관계를 가집니다.
```python
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from db import Base

class UserPreference(Base):
    __tablename__ = "preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    preferred_style = Column(String, default="") # 쉼표로 구분된 스타일 문자열

    user = relationship("User", back_populates="preferences")
```
*   `__tablename__ = "preferences"`: 이 모델이 데이터베이스의 `preferences` 테이블에 매핑됨을 나타냅니다.
*   `user_id`: `users` 테이블의 `id`를 참조하는 외래 키입니다. `unique=True`로 설정하여 각 사용자가 하나의 선호도 항목만 가지도록 합니다.
*   `preferred_style`: 사용자가 선택한 선호 스타일을 저장하는 컬럼입니다. 여러 스타일이 선택될 경우, 이들은 **쉼표로 구분된 단일 문자열** 형태로 저장됩니다 (예: "casual,formal,street").

### 3. `routers/router_survey.py` (수정)
설문조사 제출을 처리하는 `submit_survey` 엔드포인트의 로직을 수정하여 선호 스타일 데이터를 데이터베이스에 저장하도록 했습니다.
```python
from fastapi import APIRouter, Request, Depends, HTTPException, status
from dependencies import login_required
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from db import get_db
from models.models_auth import User
from models.models_preference import UserPreference
from crud.user_crud import get_user_by_username
from schemas.schemas_survey import SurveyCreate

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def survey(request: Request):
    return templates.TemplateResponse("survey/survey.html", {"request": request})

@router.post("/", response_class=JSONResponse)
async def submit_survey(
    survey_data: SurveyCreate,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    user = get_user_by_username(db, user_name)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 스타일 리스트를 쉼표로 구분된 문자열로 변환
    preferred_style_str = ",".join(survey_data.styles)

    # 사용자의 기존 선호도 정보 조회
    user_preference = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()

    if user_preference:
        # 기존 선호도 정보 업데이트
        user_preference.preferred_style = preferred_style_str
    else:
        # 새로운 선호도 정보 생성
        new_preference = UserPreference(user_id=user.id, preferred_style=preferred_style_str)
        db.add(new_preference)

    db.commit()
    db.refresh(user_preference or new_preference)

    return {"message": "Survey data received and saved successfully!", "selected_styles": survey_data.styles}
```
*   `SurveyCreate` 스키마를 사용하여 들어오는 데이터를 유효성 검사합니다.
*   `get_db`를 통해 데이터베이스 세션을 얻고, `login_required`를 통해 현재 로그인된 사용자의 `user_name`을 가져옵니다.
*   `get_user_by_username`을 사용하여 `User` 객체를 조회하고, 해당 `user_id`를 얻습니다.
*   `UserPreference` 테이블에서 해당 `user_id`에 대한 기존 항목이 있는지 확인합니다.
*   기존 항목이 있다면 `preferred_style` 필드를 업데이트하고, 없다면 새로운 `UserPreference` 객체를 생성하여 데이터베이스에 추가합니다.
*   변경 사항을 커밋하고 세션을 새로 고칩니다.

## 데이터베이스 저장 방식 요약
*   **테이블:** `preferences`
*   **컬럼:**
    *   `id` (Primary Key)
    *   `user_id` (Integer, Foreign Key to `users.id`, Unique)
    *   `preferred_style` (String, 쉼표로 구분된 스타일 문자열)

이제 사용자가 설문조사를 제출하면 선택한 선호 스타일이 데이터베이스의 `preferences` 테이블에 올바르게 저장됩니다.
