from fastapi import APIRouter, Request, Query, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import re
import random
import math
from data_store import clothing_data, processed_clothing_data
from utils.safe_utils import safe_lower, safe_str

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def process_product_data(products):
    """상품 데이터를 필터링에 필요한 형태로 가공합니다."""
    processed_products = []
    
    for product in products:
        processed_product = product.copy()
        # S3 데이터 호환: 대표이미지URL 필드 보장
        if '대표이미지URL' not in processed_product:
            processed_product['대표이미지URL'] = processed_product.get('이미지URL', processed_product.get('사진', ''))
        
        # 가격 정보 처리 - 원가만 사용
        price_value = product.get('가격', 0)
        if isinstance(price_value, (int, float)):
            processed_product['processed_price'] = int(price_value)
        else:
            # 원가만 사용
            original_price = product.get('원가', 0)
            
            if isinstance(original_price, (int, float)):
                processed_product['processed_price'] = int(original_price)
            else:
                processed_product['processed_price'] = 0
        
        # 성별 판단 (상품명과 브랜드 기반) - 새로운 컬럼명 사용
        product_name = safe_lower(product.get('상품명', ''))
        brand = safe_lower(product.get('한글브랜드명', product.get('브랜드', '')))
        
        if any(word in product_name for word in ['우먼', 'women', '여성', 'lady', '여자']):
            processed_product['성별'] = '여성'
        elif any(word in product_name for word in ['남성', 'men', 'man', '남자']):
            processed_product['성별'] = '남성'
        elif any(word in product_name for word in ['unisex', '유니섹스']):
            processed_product['성별'] = '유니섹스'
        else:
            processed_product['성별'] = '여성'  # 기본값
        
        # 의류 타입 판단
        if any(word in product_name for word in ['티셔츠', 't-shirt', 'tshirt', '티', 'shirt']):
            processed_product['의류타입'] = '상의'
            processed_product['소분류'] = '티셔츠'
        elif any(word in product_name for word in ['맨투맨', '후드', 'sweatshirt', 'hoodie', '맨투맨']):
            processed_product['의류타입'] = '상의'
            processed_product['소분류'] = '맨투맨/후드'
        elif any(word in product_name for word in ['셔츠', 'blouse', '블라우스']):
            processed_product['의류타입'] = '상의'
            processed_product['소분류'] = '셔츠/블라우스'
        elif any(word in product_name for word in ['니트', 'knit', '스웨터']):
            processed_product['의류타입'] = '상의'
            processed_product['소분류'] = '니트'
        elif any(word in product_name for word in ['민소매', '탑', 'top', '크롭']):
            processed_product['의류타입'] = '상의'
            processed_product['소분류'] = '민소매'
        elif any(word in product_name for word in ['바지', '팬츠', 'pants', 'jeans', '청바지']):
            processed_product['의류타입'] = '하의'
            if any(word in product_name for word in ['청바지', 'jeans']):
                processed_product['소분류'] = '청바지'
            elif any(word in product_name for word in ['반바지', 'shorts']):
                processed_product['소분류'] = '반바지'
            elif any(word in product_name for word in ['레깅스', 'leggings']):
                processed_product['소분류'] = '레깅스'
            elif any(word in product_name for word in ['조거', 'jogger']):
                processed_product['소분류'] = '조거팬츠'
            else:
                processed_product['소분류'] = '팬츠'
        elif any(word in product_name for word in ['스커트', 'skirt']):
            processed_product['의류타입'] = '스커트'
            if any(word in product_name for word in ['미니', 'mini']):
                processed_product['소분류'] = '미니스커트'
            elif any(word in product_name for word in ['미디', 'midi']):
                processed_product['소분류'] = '미디스커트'
            elif any(word in product_name for word in ['맥시', 'maxi']):
                processed_product['소분류'] = '맥시스커트'
            elif any(word in product_name for word in ['플리츠', 'pleated']):
                processed_product['소분류'] = '플리츠스커트'
            elif any(word in product_name for word in ['a라인', 'a-line']):
                processed_product['소분류'] = 'A라인스커트'
            else:
                processed_product['소분류'] = '스커트'
        else:
            processed_product['의류타입'] = '상의'  # 기본값
            processed_product['소분류'] = '기타'
        
        # 평점 처리 - 실제 평점이 있으면 사용, 없으면 None
        original_rating = product.get('평점', product.get('rating', None))
        if original_rating and isinstance(original_rating, (int, float)) and 0 <= original_rating <= 5:
            processed_product['평점'] = round(float(original_rating), 1)
        else:
            processed_product['평점'] = None

        # 필터 호환을 위한 영어 키 추가 (gender/type/subcategory)
        gender_map = {"여성": "female", "남성": "male", "유니섹스": "unisex"}
        type_map = {"상의": "top", "하의": "bottom", "스커트": "skirt"}
        sub_map = {
            # 상의
            "티셔츠": "tshirt",
            "맨투맨/후드": "sweatshirt",
            "셔츠/블라우스": "shirt",
            "니트": "knit",
            "민소매": "sleeveless",
            # 하의
            "청바지": "jeans",
            "팬츠": "pants",
            "반바지": "shorts",
            "레깅스": "leggings",
            "조거팬츠": "joggers",
            # 스커트 계열
            "스커트": "skirt",
            "미니스커트": "mini",
            "미디스커트": "midi",
            "맥시스커트": "maxi",
            "플리츠스커트": "pleated",
            "A라인스커트": "a_line",
        }

        processed_product['gender_key'] = gender_map.get(processed_product.get('성별', ''), '')
        processed_product['type_key'] = type_map.get(processed_product.get('의류타입', ''), '')
        processed_product['subcat_key'] = sub_map.get(processed_product.get('소분류', ''), '')
        
        processed_products.append(processed_product)
    
    return processed_products

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def products(
    request: Request, 
    page: int = Query(1, ge=1),
    gender: str = Query(None),
    clothing_type: str = Query(None),
    min_price: int = Query(None),
    max_price: int = Query(None),
    sort: str = Query(None)
):
    # processed_clothing_data 사용 (필터링에 최적화된 데이터)
    products_to_filter = processed_clothing_data if processed_clothing_data else clothing_data
    
    # 필터링 적용
    filtered_products = []
    for product in products_to_filter:
        include_product = True
        
        # 성별 필터 - gender_key 사용
        if gender:
            gender_list = gender.split(',')
            product_gender = product.get('gender_key', '').lower()
            if not any(g.lower() in product_gender for g in gender_list):
                include_product = False
        
        # 타입 필터 - type_key 사용
        if clothing_type:
            type_list = clothing_type.split(',')
            product_type = product.get('type_key', '').lower()
            if not any(t.lower() in product_type for t in type_list):
                include_product = False
        
        # 가격 필터 - processed_price 사용
        if min_price is not None:
            product_price = product.get('processed_price', 0)
            if product_price < min_price:
                include_product = False
        
        if max_price is not None:
            product_price = product.get('processed_price', 0)
            if product_price > max_price:
                include_product = False
        
        if include_product:
            filtered_products.append(product)
    
    # 정렬 적용
    if sort:
        if sort == 'price-low':
            filtered_products.sort(key=lambda x: x.get('processed_price', 0))
        elif sort == 'price-high':
            filtered_products.sort(key=lambda x: x.get('processed_price', 0), reverse=True)
        elif sort == 'name':
            filtered_products.sort(key=lambda x: x.get('상품명', '') or '')
    
    # 페이지네이션 설정
    items_per_page = 20
    total_products = len(filtered_products)
    total_pages = (total_products + items_per_page - 1) // items_per_page if total_products > 0 else 1
    
    # 현재 페이지에 해당하는 상품들 가져오기
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    display_products = filtered_products[start_idx:end_idx]
    
    # 현재 필터 상태를 URL 파라미터로 구성
    current_filters = {}
    if gender:
        current_filters['gender'] = gender
    if clothing_type:
        current_filters['clothing_type'] = clothing_type
    if min_price is not None:
        current_filters['min_price'] = min_price
    if max_price is not None:
        current_filters['max_price'] = max_price
    if sort:
        current_filters['sort'] = sort
    
    return templates.TemplateResponse("products/category_browse.html", {
        "request": request, 
        "products": display_products,
        "current_page": page,
        "total_pages": total_pages,
        "total_products": total_products,
        "items_per_page": items_per_page,
        "current_filters": current_filters
    })

@router.get("/api/products", response_class=JSONResponse)
async def get_products_api(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    gender: str = Query(None),
    clothing_type: str = Query(None),
    subcategory: str = Query(None),
    min_price: int = Query(None),
    max_price: int = Query(None),
    min_rating: float = Query(None),
    brand: str = Query(None),
    sort: str = Query(None)
):
    """API endpoint for getting filtered products"""
    # 필터링 적용
    filtered_products = []
    for product in processed_clothing_data:
        include_product = True
        
        if gender and product.get('gender_key', '') != gender:
            include_product = False
        if clothing_type and product.get('type_key', '') != clothing_type:
            include_product = False
        if subcategory and product.get('subcat_key', '') != subcategory:
            include_product = False
        if min_price is not None and product.get('processed_price', 0) < min_price:
            include_product = False
        if max_price is not None and product.get('processed_price', 0) > max_price:
            include_product = False
        if min_rating is not None and product.get('평점', 0) < min_rating:
            include_product = False
        if brand and safe_lower(brand) not in safe_lower(product.get('브랜드', '')):
            include_product = False
            
        if include_product:
            filtered_products.append(product)
    
    # 정렬 적용
    if sort:
        if sort == 'price-low':
            filtered_products.sort(key=lambda x: x.get('processed_price', 0))
        elif sort == 'price-high':
            filtered_products.sort(key=lambda x: x.get('processed_price', 0), reverse=True)
        elif sort == 'name':
            filtered_products.sort(key=lambda x: x.get('상품명', '') or '')
    
    # 페이지네이션
    total = len(filtered_products)
    total_pages = math.ceil(total / limit) if total > 0 else 1
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_products = filtered_products[start_idx:end_idx]
    
    return {
        "products": paginated_products,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_more": end_idx < total
    }