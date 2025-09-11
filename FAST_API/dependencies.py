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


# ============================================
# 이미지 추천용 카테고리 분류 (하이브리드 V2)
# ============================================
import os
import asyncio
from typing import Tuple
from openai import AsyncOpenAI

# --- GPT 설정 ---
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GPT_MODEL = "gpt-4o-mini"

# --- 카테고리 매핑 테이블 (소분류 -> 대분류) ---
# 각 모듈의 소분류 리스트를 기반으로 생성
TOP_SUB_CATS = ['후드티', '셔츠블라우스', '긴소매', '반소매', '피케카라', '니트스웨터', '슬리브리스']
PANTS_SUB_CATS = ['데님팬츠', '트레이닝조거팬츠', '코튼팬츠', '슈트팬츠슬랙스', '슈트슬랙스', '숏팬츠', '레깅스', '카고팬츠']
DRESS_SUB_CATS = ['미니원피스', '미디원피스', '맥시원피스']
SKIRT_SUB_CATS = ['미니스커트', '미디스커트', '롱스커트']

# 소분류명으로 대분류를 찾기 위한 역방향 맵
SUB_TO_MAJOR_MAP = {
    **{sub.lower(): 'top' for sub in TOP_SUB_CATS},
    **{sub.lower(): 'pants' for sub in PANTS_SUB_CATS},
    **{sub.lower(): 'dress' for sub in DRESS_SUB_CATS},
    **{sub.lower(): 'skirt' for sub in SKIRT_SUB_CATS},
}

# --- 대분류 동의어 매핑 테이블 ---
MAJOR_SYNONYM_MAP = {
    'top': ['상의', '윗옷', '탑', '티', '셔츠', '블라우스', '스웨터', '니트'],
    'pants': ['하의', '바지', '팬츠', '청바지', '슬랙스', '조거'],
    'dress': ['드레스', '원피스'],
    'skirt': ['스커트', '치마'],
}

# --- GPT 프롬프트 (대분류 추론용) ---
GPT_PROMPT_MAJOR_CAT = '''
You are a text classifier. Classify the user's input into 'top', 'pants', 'dress', or 'skirt'.
The user input is: "{user_input}"
Return only the single category name in English. If it does not fit, return 'unknown'.
'''

async def _get_major_category_from_gpt(user_input: str) -> str:
    """GPT를 사용하여 사용자 입력에서 대분류를 추론합니다."""
    try:
        response = await aclient.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": GPT_PROMPT_MAJOR_CAT.format(user_input=user_input)}
            ],
            max_tokens=10,
            temperature=0.0,
        )
        result = response.choices[0].message.content.strip().lower()
        return result if result in ['top', 'pants', 'dress', 'skirt'] else 'unknown'
    except Exception:
        return 'unknown'

async def get_category_info(user_input: str) -> Tuple[str | None, str | None]:
    """
    로직
    1. (가장 구체적인) 소분류 키워드가 문장에 포함되어 있는지 먼저 확인합니다. (예: "청바지 추천" → "청바지" 발견)
    2. 소분류가 없으면, (더 일반적인) 대분류 키워드가 문장에 포함되어 있는지 확인합니다. (예: "바지 추천" → "바지" 발견)
    3. 키워드를 전혀 찾지 못하면 GPT에게 분류를 요청합니다.
    Returns:
        Tuple[str | None, str | None]: (대분류 영문명, 소분류 한글명 또는 None)
    """
    user_input_norm = user_input.lower().strip()

    # 1. 소분류 키워드 포함 여부 확인 (가장 구체적인 것부터)
    for sub_cat_keyword, major_cat in SUB_TO_MAJOR_MAP.items():
        if sub_cat_keyword in user_input_norm:
            return major_cat, sub_cat_keyword
        
    # 2. 대분류 동의어 포함 여부 확인
    for major_cat, synonyms in MAJOR_SYNONYM_MAP.items():
        for s in synonyms:
            if s.lower() in user_input_norm:
                return major_cat, None
            
    # 3. GPT로 대분류 추론 (위에서 키워드를 못찾았을 경우)
    major_cat_gpt = await _get_major_category_from_gpt(user_input)
    if major_cat_gpt != 'unknown':
        return major_cat_gpt, None

    # 4. 어느 것에도 해당하지 않음
    return None, None