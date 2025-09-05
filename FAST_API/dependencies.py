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

# 소분류명으로 대분류를 찾기 위한 역방향 맵
SUB_TO_MAJOR_MAP = {
    **{sub.lower(): 'top' for sub in TOP_SUB_CATS},
    **{sub.lower(): 'pants' for sub in PANTS_SUB_CATS},
    **{sub.lower(): 'dress' for sub in DRESS_SUB_CATS},
}

# --- 대분류 동의어 매핑 테이블 ---
MAJOR_SYNONYM_MAP = {
    'top': ['상의', '윗옷', '탑', '티', '셔츠', '블라우스', '스웨터', '니트'],
    'pants': ['하의', '바지', '팬츠', '청바지', '슬랙스', '조거'],
    'dress': ['드레스', '원피스'],
}

# --- GPT 프롬프트 (대분류 추론용) ---
GPT_PROMPT_MAJOR_CAT = '''
You are a text classifier. Classify the user's input into 'top', 'pants', or 'dress'.
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
        return result if result in ['top', 'pants', 'dress'] else 'unknown'
    except Exception:
        return 'unknown'

async def get_category_info(user_input: str) -> Tuple[str | None, str | None]:
    """
    사용자 입력을 분석하여 (대분류, 소분류) 정보를 반환합니다.

    - 시나리오 1 (소분류 입력): "후드티" -> ('top', '후드티')
    - 시나리오 2 (대분류 입력): "윗옷" -> ('top', None)
    - 시나리오 3 (GPT 필요): "이 잠바" -> ('top', None)

    Returns:
        Tuple[str | None, str | None]: (대분류 영문명, 소분류 한글명 또는 None)
    """
    user_input_norm = user_input.lower().strip()

    # 1. 소분류 맵에서 직접 조회 (시나리오 2)
    if user_input_norm in SUB_TO_MAJOR_MAP:
        major_cat = SUB_TO_MAJOR_MAP[user_input_norm]
        return major_cat, user_input # 원본 소분류명 반환

    # 2. 대분류 동의어 맵에서 조회 (시나리오 1의 일부)
    for major_cat, synonyms in MAJOR_SYNONYM_MAP.items():
        if user_input_norm in [s.lower() for s in synonyms]:
            return major_cat, None # 대분류만 확정, 소분류는 모름

    # 3. GPT로 대분류 추론 (시나리오 1의 일부)
    major_cat_gpt = await _get_major_category_from_gpt(user_input)
    if major_cat_gpt != 'unknown':
        return major_cat_gpt, None # 대분류만 확정, 소분류는 모름

    # 4. 어느 것에도 해당하지 않음
    return None, None


# ============================================
# 이미지 추천용 카테고리 분류 (하이브리드)
# ============================================
import os
import asyncio
from openai import AsyncOpenAI

# --- GPT 설정 ---
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GPT_MODEL = "gpt-4o-mini"

# --- 카테고리 매핑 테이블 ---
CATEGORY_MAP = {
    'top': [
        # 일반 동의어
        '상의', '윗옷', '탑', '티', '셔츠', '블라우스', '스웨터', '니트',
        # 모듈 소분류
        '후드티', '셔츠블라우스', '긴소매', '반소매', '피케카라', '니트스웨터', '슬리브리스'
    ],
    'pants': [
        # 일반 동의어
        '하의', '바지', '팬츠', '청바지', '슬랙스', '조거',
        # 모듈 소분류
        '데님팬츠', '트레이닝조거팬츠', '코튼팬츠', '슈트팬츠슬랙스', '슈트슬랙스', '숏팬츠', '레깅스', '카고팬츠'
    ],
    'dress': [
        # 일반 동의어
        '드레스', '원피스',
        # 모듈 소분류
        '미니원피스', '미디원피스', '맥시원피스'
    ]
}

# --- GPT 프롬프트 ---
GPT_PROMPT_TEMPLATE = '''
You are a text classifier. Your task is to classify the user's input into one of the following three categories: 'top', 'pants', 'dress'.
The user's input is in Korean.
The user input is: "{user_input}"
Return only the single category name in English ('top', 'pants', or 'dress'). If it does not fit any of these, return 'unknown'.
'''

async def _get_category_from_gpt(user_input: str) -> str:
    """GPT를 사용하여 사용자 입력을 카테고리로 분류합니다."""
    try:
        response = await aclient.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": GPT_PROMPT_TEMPLATE.format(user_input=user_input)}
            ],
            max_tokens=10,
            temperature=0.0,
        )
        result = response.choices[0].message.content.strip().lower()
        if result in ['top', 'pants', 'dress']:
            return result
        return 'unknown'
    except Exception:
        return 'unknown'

async def normalize_category_hybrid(user_input: str) -> str:
    """
    사용자 입력을 표준 카테고리명으로 변환합니다 (하이브리드 방식).
    1. 매핑 테이블에서 조회
    2. 실패 시 GPT로 분류
    """
    # 1. 매핑 테이블에서 조회
    user_input_normalized = user_input.lower().strip()
    for standard_name, synonyms in CATEGORY_MAP.items():
        # 한국어 소분류명 등을 위해 소문자 변환 후 비교
        if user_input_normalized in [s.lower() for s in synonyms]:
            return standard_name

    # 2. GPT로 분류 (매핑 실패 시)
    return await _get_category_from_gpt(user_input)
