from fastapi import APIRouter, Request, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from data_store import clothing_data
from db import get_db
from sqlalchemy.orm import Session
from crud.user_crud import (
    get_trending_products, 
    get_personalized_recommendations, 
    get_preference_by_user_id,
    filter_products_by_color
)
import random

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 스타일-카테고리 하드코딩 맵
STYLE_TO_CATEGORY_MAP = {
    "Casual": ["후드티", "긴소매", "반소매", "피케카라", "니트스웨터", "데님 팬츠", "코튼 팬츠", "슈트 팬츠/슬랙스", "숏 팬츠", "트레이닝/조거 팬츠", "카고팬츠"],
    "Street": ["후드티", "긴소매", "반소매", "슬리브리스", "데님 팬츠", "트레이닝/조거 팬츠", "카고팬츠", "숏 팬츠"],
    "Formal": ["셔츠블라우스", "긴소매", "니트스웨터", "슈트 팬츠/슬랙스", "미니원피스", "미디원피스", "맥시원피스", "미니스커트", "미디스커트", "롱스커트"],
    "Minimal": ["셔츠블라우스", "긴소매", "니트스웨터", "슬리브리스", "슈트 팬츠/슬랙스", "코튼 팬츠", "미디원피스", "롱스커트"]
}

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def read_home(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get('user_id')
    if not user_id:
        return templates.TemplateResponse("error.html", {"request": request, "message": "로그인이 필요합니다."})

    user_pref = get_preference_by_user_id(db, user_id)
    show_survey_modal = not (user_pref and user_pref.survey_completed)

    # --- 섹션 1: "님이 좋아할 만한 콘텐츠" (설문조사 기반 1차 필터링 + 체형 기반 2차 필터링 + 대체 로직) ---
    section1_items = []
    if user_pref and user_pref.preferred_style:
        preferred_style = user_pref.preferred_style
        target_categories = STYLE_TO_CATEGORY_MAP.get(preferred_style, [])

        if target_categories:
            # 1. 전체 상품 데이터에서 선호 스타일에 맞는 상품만 1차 필터링
            style_filtered_clothing_data = [
                product for product in clothing_data
                if product.get('소분류') in target_categories
            ]

            # 2. 1차 필터링된 상품들 중에서 체형 기반 추천 로직 적용
            if style_filtered_clothing_data:
                # get_personalized_recommendations는 product_id와 jjim_count만 반환
                # product_pool_ids_set을 get_personalized_recommendations에 전달해야 함
                # 현재 get_personalized_recommendations는 product_pool_ids_set을 받지 않으므로,
                # 이 부분은 router_home.py에서 직접 필터링 로직을 구현합니다.
                
                # get_personalized_recommendations는 전체 상품에서 유사 사용자 찜 목록 ID를 가져옴
                personalized_data_ids_only = get_personalized_recommendations(db, user_id, limit=100) # 후보군 확보
                personalized_ids_set = {item['product_id'] for item in personalized_data_ids_only}

                # style_filtered_clothing_data 내에서 personalized_ids_set에 있는 상품만 선택
                combined_filtered_products = []
                for product in style_filtered_clothing_data:
                    if product.get('상품코드') in personalized_ids_set:
                        # 찜 횟수 정보 추가
                        jjim_count = next((item['jjim_count'] for item in personalized_data_ids_only if item['product_id'] == product.get('상품코드')), 0)
                        product_with_count = product.copy()
                        product_with_count['jjim_count'] = jjim_count
                        combined_filtered_products.append(product_with_count)
                
                # 3. 대체 로직: 2차 필터링 결과가 없으면 1차 필터링 결과 사용
                if not combined_filtered_products:
                    section1_items = style_filtered_clothing_data # 2차 필터링 결과가 없으면 1차 결과 사용
                else:
                    section1_items = combined_filtered_products # 2차 필터링 결과가 있으면 그것을 사용

    # 사용자 선호 색상으로 필터링 (최종 단계)
    if user_pref and user_pref.preferred_color:
        section1_items = filter_products_by_color(section1_items, user_pref.preferred_color)

    # 최종적으로 찜 순으로 정렬하여 상위 아이템 선택 (대체 로직 후에도 적용)
    section1_items.sort(key=lambda x: x.get('jjim_count', 0), reverse=True)
    section1_items = section1_items[:20]

    # --- 섹션 2: "지금 뜨는 콘텐츠" (전체 인기 상품) ---
    trending_data = get_trending_products(db, limit=20)
    # 찜 횟수를 쉽게 조회할 수 있도록 상품 ID를 키로 하는 딕셔너리 생성
    trending_ids_with_counts = {item['product_id']: item['jjim_count'] for item in trending_data}
    
    section2_items = []
    processed_ids = set()  # 중복 추가를 방지하기 위한 ID 세트

    # clothing_data에서 인기 상품 정보를 찾되, 중복을 제거
    for product in clothing_data:
        product_id = product.get('상품코드')
        if product_id in trending_ids_with_counts and product_id not in processed_ids:
            product_with_count = product.copy()
            product_with_count['jjim_count'] = trending_ids_with_counts[product_id]
            section2_items.append(product_with_count)
            processed_ids.add(product_id)  # 처리된 ID로 기록

    # 찜 횟수 순으로 최종 정렬
    section2_items.sort(key=lambda x: x.get('jjim_count', 0), reverse=True)

    # --- 섹션 3 & 4: 랜덤 추천 (중복 방지) ---
    used_ids = {p.get('상품코드') for p in section1_items}.union({p.get('상품코드') for p in section2_items})
    remaining_products = [p for p in clothing_data if p.get('상품코드') not in used_ids]
    
    # 섹션 3
    section3_items = random.sample(remaining_products, min(len(remaining_products), 20))
    used_ids.update({p.get('상품코드') for p in section3_items})
    remaining_products = [p for p in remaining_products if p.get('상품코드') not in used_ids]

    # 섹션 4
    section4_items = random.sample(remaining_products, min(len(remaining_products), 20))

    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request, 
            "section1_items": section1_items,
            "section2_items": section2_items,
            "section3_items": section3_items,
            "section4_items": section4_items,
            "show_survey_modal": show_survey_modal
        }
    )