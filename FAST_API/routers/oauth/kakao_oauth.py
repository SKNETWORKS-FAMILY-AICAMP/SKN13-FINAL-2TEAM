# routers/oauth/kakao_oauth.py

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from typing import Optional
import os
import uuid

# 내부 의존성
from db import get_db
from crud.user_crud import get_user_by_email, get_user_by_username
from models.models_auth import User

load_dotenv()
router = APIRouter()

# ======================
# OAuth 클라이언트 등록
# ======================
oauth = OAuth()
oauth.register(
    name="kakao",
    client_id=os.getenv("KAKAO_CLIENT_ID"),                      # REST API 키
    client_secret=os.getenv("KAKAO_CLIENT_SECRET", None),        # 콘솔에서 사용하는 경우에만
    access_token_url="https://kauth.kakao.com/oauth/token",
    authorize_url="https://kauth.kakao.com/oauth/authorize",
    api_base_url="https://kapi.kakao.com/v2/",
    client_kwargs={
        # 이메일까지 필요하면 account_email을 동의항목에서 ON 하고 scope에 포함
        "scope": os.getenv(
            "KAKAO_SCOPES",
            "profile_nickname profile_image account_email"
        )
    },
)

# ======================
# 유틸: 소셜 업서트 & 세션
# ======================
def upsert_user_from_kakao(
    db: Session,
    kakao_id: str,
    email: Optional[str],
    nickname: Optional[str],
) -> User:
    # 1) 이메일이 있으면 이메일 기준으로 기존 계정 연결
    user = get_user_by_email(db, email) if email else None

    if not user:
        # 2) 신규 생성 (username 충돌 회피)
        base_username = (nickname or f"kakao_{kakao_id}").strip()
        username = base_username
        i = 1
        while get_user_by_username(db, username):
            username = f"{base_username}_{i}"
            i += 1

        user = User(
            username=username,
            password="",        # 소셜 계정은 비번 미사용 (정책에 따라 별도 처리 가능)
            email=email,
            role="user",
        )
        # 선택: 모델에 oauth_provider/oauth_sub 칼럼이 있으면 저장
        if hasattr(user, "oauth_provider"):
            user.oauth_provider = "kakao"
        if hasattr(user, "oauth_sub"):
            user.oauth_sub = kakao_id

        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # 3) 기존 계정이면 provider/sub 업데이트 (칼럼 있을 때)
        dirty = False
        if hasattr(user, "oauth_provider") and not getattr(user, "oauth_provider", None):
            user.oauth_provider = "kakao"; dirty = True
        if hasattr(user, "oauth_sub") and not getattr(user, "oauth_sub", None):
            user.oauth_sub = kakao_id; dirty = True
        if dirty:
            db.commit()
            db.refresh(user)
    return user


def set_login_session(request: Request, user: User):
    # 기존 세션 데이터 삭제 후 새로운 세션 생성
    request.session.clear()
    
    # 로컬 로그인과 동일한 세션 키 사용 (중요)
    request.session["user_name"] = user.username
    request.session["user_id"]  = user.id
    request.session["role"]     = user.role or "user"
    request.session["login_time"] = str(uuid.uuid4())  # 고유한 로그인 식별자


# ======================
# 라우트
# ======================
@router.get("/kakao/login")
async def kakao_login(request: Request):
    # 로그인 후 돌아갈 경로 지원: /auth/kakao/login?next=/mypage
    next_url = request.query_params.get("next")
    if next_url:
        request.session["next_url"] = next_url

    redirect_uri = os.getenv("KAKAO_REDIRECT_URI")  # 예: http://localhost:8000/auth/kakao/callback
    return await oauth.kakao.authorize_redirect(request, redirect_uri)


@router.get("/kakao/callback")
async def kakao_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.kakao.authorize_access_token(request)
        # base_url이 https://kapi.kakao.com/v2/ 이므로 path만 넘기면 됨
        resp = await oauth.kakao.get("user/me", token=token)
        data = resp.json()

        kakao_id = str(data.get("id"))
        kakao_account = data.get("kakao_account", {}) or {}
        profile = kakao_account.get("profile", {}) or {}

        nickname = profile.get("nickname")
        email = kakao_account.get("email")  # 사용자가 이메일 동의를 거부하면 None

        # DB 업서트 → 내부 유저 획득
        user = upsert_user_from_kakao(db, kakao_id=kakao_id, email=email, nickname=nickname)

        # 세션 저장 (로컬과 동일 포맷)
        set_login_session(request, user)

        # 원래 가려던 경로로 이동
        next_url = request.session.pop("next_url", "/")
        return RedirectResponse(url=next_url)

    except Exception as e:
        print("Kakao OAuth Error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
