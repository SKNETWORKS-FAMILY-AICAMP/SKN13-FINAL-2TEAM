# 설문조사 기능 변경 사항 (데이터베이스 마이그레이션 보류 중)

이 문서는 `user_preferences` 테이블의 `survey_completed` 컬럼에 대한 데이터베이스 스키마 마이그레이션이 보류 중이므로, 설문조사 기능과 관련된 변경 사항들이 일시적으로 주석 처리되거나 되돌려졌음을 설명합니다.

**주석 처리/되돌린 이유:**
현재 데이터베이스 스키마에는 `user_preferences.survey_completed` 컬럼이 존재하지 않습니다. 이 컬럼을 사용하려고 시도할 경우(예: `get_preference_by_user_id` 또는 `upsert_user_preference`에서) `ProgrammingError: UndefinedColumn` 오류가 발생합니다.

**"첫 로그인 시 설문조사 표시" 기능을 완전히 활성화하려면, `user_preferences` 테이블에 `survey_completed` 컬럼을 포함하도록 데이터베이스 스키마를 업데이트해야 합니다.**

## 영향받는 파일 및 변경 사항:

### 1. `models/models_mypage.py`
- **변경 내용:** `survey_completed` 컬럼 정의가 추가되었다가 되돌려졌습니다.
- **원래 변경 내용 (DB 마이그레이션 후 다시 적용):**
  ```python
  from sqlalchemy import Column, Integer, String, ForeignKey, Boolean # Boolean 추가
  from sqlalchemy.orm import relationship
  from db import Base


  class UserPreference(Base):
      __tablename__ = "user_preferences"

      prefer_id = Column(Integer, primary_key=True, index=True)
      user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
      height = Column(Integer, nullable=True)
      weight = Column(Integer, nullable=True)
      preferred_color = Column(String(50), nullable=True)
      preferred_style = Column(String(100), nullable=True)
      survey_completed = Column(Boolean, default=False) # 이 줄을 추가

      user = relationship("models.models_auth.User", back_populates="preferences")
  ```

### 2. `crud/user_crud.py`
- **변경 내용:** `upsert_user_preference` 함수가 `survey_completed`를 받아 업데이트하도록 수정되었다가 되돌려졌습니다.
- **원래 변경 내용 (DB 마이그레이션 후 다시 적용):**
  ```python
  # upsert_user_preference 함수 내:
  def upsert_user_preference(
      db: Session,
      user_id: int,
      *,
      height: Optional[int] = None,
      weight: Optional[int] = None,
      preferred_color: Optional[str] = None,
      preferred_style: Optional[str] = None,
      survey_completed: Optional[bool] = None, # 이 매개변수 추가
  ) -> UserPreference:
      # ... (기존 코드) ...
      if pref is None:
          pref = UserPreference(
              # ... (기존 매개변수) ...
              survey_completed=survey_completed if survey_completed is not None else False, # 이 줄을 추가
          )
          db.add(pref)
      else:
          # ... (기존 업데이트) ...
          if survey_completed is not None:
              pref.survey_completed = survey_completed
      db.commit()
      db.refresh(pref)
      return pref
  ```

### 3. `routers/router_auth.py`
- **변경 내용:** `login_post` 함수의 설문조사 리디렉션 로직과 `get_preference_by_user_id` 임포트가 주석 처리되었습니다.
- **원래 변경 내용 (DB 마이그레이션 후 주석 해제):**
  ```python
  # login_post 함수 내:
  # 다음 블록의 주석을 해제:
  # user_preference = get_preference_by_user_id(db, user.id)
  # if not user_preference or not user_preference.survey_completed:
  #     return RedirectResponse(url="/survey/", status_code=status.HTTP_302_FOUND)

  # 임포트 주석 해제:
  # from crud.user_crud import get_preference_by_user_id
  ```

### 4. `routers/router_survey.py`
- **변경 내용:** `submit_survey` 함수가 `survey_completed`를 업데이트하고 리디렉션하도록 수정되었다가 원래 상태로 되돌려졌습니다.
- **원래 변경 내용 (DB 마이그레이션 후 다시 적용):**
  ```python
  # submit_survey 함수 내:
  # response_class를 RedirectResponse로 변경
  # dependencies=[Depends(login_required)] 추가
  # db: Session = Depends(get_db) 매개변수 추가
  # 사용자 정보를 가져와 upsert_user_preference를 survey_completed=True로 호출하는 로직 추가
  # return을 RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)로 변경
  ```

## 기능 재활성화 방법:

1.  **데이터베이스 마이그레이션 수행:**
    -   `user_preferences` 테이블에 `survey_completed` 컬럼이 포함되도록 데이터베이스 스키마를 업데이트해야 합니다.
    -   Alembic을 사용하는 경우 다음을 실행:
        ```bash
        alembic revision --autogenerate -m "Add survey_completed to UserPreference"
        alembic upgrade head
        ```
    -   데이터베이스를 다시 생성하는 경우, `init_db()`가 컬럼을 올바르게 생성하는지 확인.
2.  **코드 변경 사항 주석 해제/다시 적용:**
    -   위에 나열된 "영향받는 파일" 각각을 확인.
    -   이전에 주석 처리된 코드를 주석 해제.
    -   설명된 대로 "원래 변경 내용" 섹션을 다시 적용.
3.  **애플리케이션 재시작:** 변경 사항을 로드하기 위해 FastAPI 애플리케이션을 재시작.