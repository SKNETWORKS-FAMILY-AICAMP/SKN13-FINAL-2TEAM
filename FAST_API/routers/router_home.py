from fastapi import APIRouter, Request, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from data_store import clothing_data
from db import get_db
from sqlalchemy.orm import Session
from crud.user_crud import get_trending_products, get_personalized_recommendations, filter_products_by_color, get_preference_by_user_id
import random

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def read_home(request: Request, db: Session = Depends(get_db)):
    """
    메인 홈페이지를 렌더링합니다.
    서버 시작 시 미리 로드된 clothing_data를 사용합니다.
    """
    # 데이터가 비어있는 경우를 대비하여 안전하게 처리 (불필요한 대량 로그 제거)
    if not clothing_data:
        sampled_data = []
    else:
        # 표시할 데이터 수를 100개 또는 전체 데이터 수 중 작은 값으로 제한
        count = min(100, len(clothing_data))
        sampled_data = random.sample(clothing_data, count)

    # 사용자 ID 가져오기
    user_id = request.session.get('user_id')
    
    # 사용자 맞춤형 추천 상품 가져오기
    personalized_products_data = get_personalized_recommendations(db, user_id, limit=20)
    
    # 사용자 맞춤형 추천 상품 ID 목록
    personalized_product_ids = {item['product_id'] for item in personalized_products_data}
    
    # 사용자 맞춤형 추천 상품 정보 가져오기
    personalized_products = []
    for product in clothing_data:
        if product.get('상품코드') in personalized_product_ids:
            # 찜 횟수 정보 추가
            jjim_count = next((item['jjim_count'] for item in personalized_products_data 
                              if item['product_id'] == product.get('상품코드')), 0)
            product_with_count = product.copy()
            product_with_count['jjim_count'] = jjim_count
            personalized_products.append(product_with_count)
    
    # 찜 횟수 순으로 정렬
    personalized_products.sort(key=lambda x: x.get('jjim_count', 0), reverse=True)
    
    # 사용자 선호 색상으로 필터링
    user_pref = get_preference_by_user_id(db, user_id)
    if user_pref and user_pref.preferred_color:
        personalized_products = filter_products_by_color(personalized_products, user_pref.preferred_color)

    # 트렌딩 상품 가져오기 (찜 횟수 기반)
    trending_products_data = get_trending_products(db, limit=20)
    
    # 트렌딩 상품 ID 목록
    trending_product_ids = {item['product_id'] for item in trending_products_data}
    
    # 트렌딩 상품 정보 가져오기
    trending_products = []
    for product in clothing_data:
        if product.get('상품코드') in trending_product_ids:
            # 찜 횟수 정보 추가
            jjim_count = next((item['jjim_count'] for item in trending_products_data 
                              if item['product_id'] == product.get('상품코드')), 0)
            product_with_count = product.copy()
            product_with_count['jjim_count'] = jjim_count
            trending_products.append(product_with_count)
    
    # 찜 횟수 순으로 정렬
    trending_products.sort(key=lambda x: x.get('jjim_count', 0), reverse=True)
    
    # 데이터를 4개의 섹션으로 분할
    section_size = len(sampled_data) // 4
    
    # 섹션 1: 사용자 맞춤 추천 (새로운 로직)
    if personalized_products:
        section1_items = personalized_products[:section_size]
    else:
        # 맞춤형 추천이 없으면 랜덤 상품으로 대체
        section1_items = sampled_data[:section_size]
    
    # 섹션 2: 지금 뜨는 콘텐츠 (트렌딩 상품)
    if trending_products:
        section2_items = trending_products[:section_size]
    else:
        # 트렌딩 상품이 없으면 랜덤 상품으로 대체
        section2_items = sampled_data[:section_size]
    
    # 나머지 상품들 (추천과 트렌딩에 포함되지 않은 것들)
    used_product_ids = personalized_product_ids.union(trending_product_ids)
    non_recommended_products = [p for p in sampled_data if p.get('상품코드') not in used_product_ids]
    
    # 섹션 3: 새로 추가된 콘텐츠 (나머지 상품들)
    section3_items = non_recommended_products[:section_size]
    
    # 섹션 4: 추가 추천 콘텐츠 (나머지 상품들)
    section4_items = non_recommended_products[section_size:section_size*2]

    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request, 
            "section1_items": section1_items,
            "section2_items": section2_items,
            "section3_items": section3_items,
            "section4_items": section4_items
        }
    )
