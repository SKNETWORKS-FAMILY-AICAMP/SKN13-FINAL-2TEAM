from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from db import get_db
from models.models_auth import User
from crud.user_crud import get_user_by_username


def login_required(request: Request):
    """세션에서 로그인 상태를 확인합니다.
    - 기본: `session['user_name']`
    - OAuth 호환: `session['user']`가 dict인 경우 표시 이름을 유도하여 채웁니다.
    - 세션 무효화 검증 추가
    """
    user_name = request.session.get("user_name")
    user_id = request.session.get("user_id")
    login_time = request.session.get("login_time")

    # 필수 세션 데이터 검증
    if not user_name or not user_id:
        oauth_user = request.session.get("user")
        if isinstance(oauth_user, dict):
            # Kakao/Google 공통 필드에서 표시 이름 추출 시도
            display = oauth_user.get("nickname") or oauth_user.get("name") or oauth_user.get("email") or str(oauth_user.get("id", ""))
            if display:
                request.session["user_name"] = display
                user_name = display

    # 세션 데이터가 불완전하면 로그인 페이지로 리다이렉트
    if not user_name or not user_id:
        # 세션 데이터 정리
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/auth/login"},
        )

    return user_name


def admin_required(request: Request, db: Session = Depends(get_db)):
    """관리자 접근 제어. 세션 사용자 조회 후 DB에서 role 확인."""
    user_name = login_required(request)
    user: User | None = get_user_by_username(db, user_name)
    if not user or (user.role or "user") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 전용 페이지입니다.")
    return user
