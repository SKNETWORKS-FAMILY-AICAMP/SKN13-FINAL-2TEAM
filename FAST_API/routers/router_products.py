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

        # 사이트명 필드 보장
        if '사이트명' not in processed_product:
            processed_product['사이트명'] = product.get('사이트명', '')

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

        # 성별 및 의류 타입 판단을 위해 상품명을 미리 정의
        product_name = safe_lower(product.get('상품명', ''))

        # 성별 판단 (원본 데이터 우선, 없을 시 상품명 기반) - 새로운 컬럼명 사용
        original_gender = safe_str(product.get('성별', '')).strip()
        if original_gender in ['남성', '여성', '공용']:
            processed_product['성별'] = original_gender
        else:
            # 키워드 기반 추측 (Fallback)
            if any(word in product_name for word in ['우먼', 'women', '여성', 'lady', '여자']):
                processed_product['성별'] = '여성'
            elif any(word in product_name for word in ['남성', 'men', 'man', '남자']):
                processed_product['성별'] = '남성'
            elif any(word in product_name for word in ['unisex', '유니섹스', '공용']):
                processed_product['성별'] = '공용'
            else:
                processed_product['성별'] = '공용'  # 기본값을 '공용'으로 변경

        # 대분류 및 소분류 판단 (S3 데이터의 '대분류', '소분류' 필드를 우선 사용)
        original_major_category = product.get('대분류', '')
        original_minor_category = product.get('소분류', '')

        if original_major_category:
            processed_product['major_category_key'] = original_major_category
        else:
            # 상품명 기반 추측 (Fallback)
            if any(word in product_name for word in ['티셔츠', 't-shirt', 'tshirt', '티', 'shirt', '맨투맨', '후드', 'sweatshirt', 'hoodie', '셔츠', 'blouse', '블라우스', '니트', 'knit', '스웨터', '민소매', '탑', 'top', '크롭']):
                processed_product['major_category_key'] = '상의'
            elif any(word in product_name for word in ['바지', '팬츠', 'pants', 'jeans', '청바지', '반바지', '레깅스', 'leggings', '조거', 'jogger']):
                processed_product['major_category_key'] = '하의'
            elif any(word in product_name for word in ['스커트', 'skirt', '미니', 'midi', '맥시', 'maxi', '플리츠', 'pleated', 'a라인', 'a-line']):
                processed_product['major_category_key'] = '스커트'
            elif any(word in product_name for word in ['원피스', '드레스', 'dress']):
                processed_product['major_category_key'] = '원피스'
            else:
                processed_product['major_category_key'] = '기타' # 기본값

        if original_minor_category:
            processed_product['minor_category_key'] = original_minor_category
        else:
            # 상품명 기반 추측 (Fallback)
            if 'major_category_key' in processed_product:
                if processed_product['major_category_key'] == '상의':
                    if any(word in product_name for word in ['긴소매', 'long sleeve']):
                        processed_product['minor_category_key'] = '긴소매'
                    elif any(word in product_name for word in ['니트', '스웨터', 'knit', 'sweater']):
                        processed_product['minor_category_key'] = '니트/스웨터'
                    elif any(word in product_name for word in ['반소매', 'short sleeve']):
                        processed_product['minor_category_key'] = '반소매'
                    elif any(word in product_name for word in ['셔츠', '블라우스', 'shirt', 'blouse']):
                        processed_product['minor_category_key'] = '셔츠/블라우스'
                    elif any(word in product_name for word in ['슬리브리스', 'sleeveless']):
                        processed_product['minor_category_key'] = '슬리브리스'
                    elif any(word in product_name for word in ['피케', '카라', 'pique', 'collar']):
                        processed_product['minor_category_key'] = '피케/카라'
                    elif any(word in product_name for word in ['후드티', 'hoodie']):
                        processed_product['minor_category_key'] = '후드티'
                    else:
                        processed_product['minor_category_key'] = '기타 상의'
                elif processed_product['major_category_key'] == '하의': # Note: '하의' is mapped from '바지' in major_category_map
                    if any(word in product_name for word in ['데님', 'denim']):
                        processed_product['minor_category_key'] = '데님팬츠'
                    elif any(word in product_name for word in ['숏', '반바지', 'short']):
                        processed_product['minor_category_key'] = '숏팬츠'
                    elif any(word in product_name for word in ['슈트', '슬랙스', 'suit', 'slacks']):
                        processed_product['minor_category_key'] = '슈트팬츠/슬랙스'
                    elif any(word in product_name for word in ['카고', 'cargo']):
                        processed_product['minor_category_key'] = '카고팬츠'
                    elif any(word in product_name for word in ['코튼', 'cotton']):
                        processed_product['minor_category_key'] = '코튼팬츠'
                    elif any(word in product_name for word in ['트레이닝', '조거', 'training', 'jogger']):
                        processed_product['minor_category_key'] = '트레이닝/조거팬츠'
                    else:
                        processed_product['minor_category_key'] = '기타 하의'
                elif processed_product['major_category_key'] == '스커트':
                    if any(word in product_name for word in ['롱', 'long']):
                        processed_product['minor_category_key'] = '롱스커트'
                    elif any(word in product_name for word in ['미니', 'mini']):
                        processed_product['minor_category_key'] = '미니스커트'
                    elif any(word in product_name for word in ['미디', 'midi']):
                        processed_product['minor_category_key'] = '미디스커트'
                    else:
                        processed_product['minor_category_key'] = '기타 스커트'
                elif processed_product['major_category_key'] == '원피스':
                    if any(word in product_name for word in ['맥시', 'maxi']):
                        processed_product['minor_category_key'] = '맥시원피스'
                    elif any(word in product_name for word in ['미니', 'mini']):
                        processed_product['minor_category_key'] = '미니원피스'
                    elif any(word in product_name for word in ['미디', 'midi']):
                        processed_product['minor_category_key'] = '미디원피스'
                    else:
                        processed_product['minor_category_key'] = '기타 원피스'
                else:
                    processed_product['minor_category_key'] = '기타'

        # 평점 처리 - 실제 평점이 있으면 사용, 없으면 None
        original_rating = product.get('평점', product.get('rating', None))
        if original_rating and isinstance(original_rating, (int, float)) and 0 <= original_rating <= 5:
            processed_product['평점'] = round(float(original_rating), 1)
        else:
            processed_product['평점'] = None

        # 필터 호환을 위한 영어 키 추가 (gender/major_category/minor_category)
        gender_map = {"여성": "female", "남성": "male", "공용": "unisex", "유니섹스": "unisex"}
        major_category_map = {"상의": "top", "하의": "bottom", "스커트": "skirt", "원피스": "onepiece"}
        minor_category_map = {
            "데님팬츠": "denim_pants", "숏팬츠": "short_pants", "슈트팬츠/슬랙스": "suit_slacks", "카고팬츠": "cargo_pants", "코튼팬츠": "cotton_pants", "트레이닝/조거팬츠": "training_jogger_pants", "슈트 팬츠/슬랙스": "suit_slacks",
            "긴소매": "long_sleeve", "니트/스웨터": "knit_sweater", "반소매": "short_sleeve", "셔츠/블라우스": "shirt_blouse", "슬리브리스": "sleeveless", "피케/카라": "pique_collar", "후드티": "hoodie",
            "롱스커트": "long_skirt", "미니스커트": "mini_skirt", "미디스커트": "midi_skirt",
            "맥시원피스": "maxi_onepiece", "미니원피스": "mini_onepiece", "미디원피스": "midi_onepiece"
        }

        processed_product['gender_key'] = gender_map.get(processed_product.get('성별', ''), '')
        processed_product['major_category_key'] = major_category_map.get(processed_product.get('major_category_key', ''), '')
        processed_product['minor_category_key_en'] = minor_category_map.get(processed_product.get('minor_category_key', ''), '')

        processed_products.append(processed_product)

    return processed_products

@router.get("/categories/major", response_class=JSONResponse)
async def get_major_categories():
    # Use the specific major categories provided by the user
    major_categories = ["상의", "바지", "스커트", "원피스"]
    return {"major_categories": major_categories}

@router.get("/categories/minor", response_class=JSONResponse)
async def get_minor_categories(major_category: str = Query(...)):
    minor_category_map_user_defined = {
        "바지": ['데님팬츠', '숏팬츠', '슈트팬츠/슬랙스', '카고팬츠', '코튼팬츠', '트레이닝/조거팬츠', '슈트 팬츠/슬랙스'],
        "상의": ['긴소매', '니트/스웨터', '반소매', '셔츠/블라우스', '슬리브리스', '피케/카라', '후드티'],
        "스커트": ['롱스커트', '미니스커트', '미디스커트'],
        "원피스": ['맥시원피스', '미니원피스', '미디원피스']
    }
    minor_categories = minor_category_map_user_defined.get(major_category, [])
    return {"minor_categories": minor_categories}

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def products(
    request: Request,
    page: int = Query(1, ge=1),
    gender: str = Query(None),
    major_category: str = Query(None), # New parameter
    minor_category: str = Query(None), # New parameter
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

        # 대분류 필터 - major_category_key 사용
        if major_category:
            major_category_list = major_category.split(',')
            product_major_category = product.get('major_category_key', '').lower()
            if not any(mc.lower() in product_major_category for mc in major_category_list):
                include_product = False

        # 소분류 필터 - minor_category_key 사용
        if minor_category:
            minor_category_list = minor_category.split(',')
            product_minor_category = product.get('minor_category_key', '').lower()
            if not any(mnc.lower() in product_minor_category for mnc in minor_category_list):
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
    if major_category: # New filter
        current_filters['major_category'] = major_category
    if minor_category: # New filter
        current_filters['minor_category'] = minor_category
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
    major_category: str = Query(None),
    minor_category: str = Query(None),
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
        
        # major_category 필터
        if major_category:
            major_category_map_reverse = {"상의": "top", "하의": "bottom", "스커트": "skirt", "원피스": "onepiece"}
            major_category_list = [major_category_map_reverse.get(mc.strip(), '') for mc in major_category.split(',') if mc.strip()]
            product_major_category = product.get('major_category_key', '').lower()
            if not any(mc_en.lower() == product_major_category for mc_en in major_category_list): # Exact match for English keys
                include_product = False

        # 소분류 필터
        if minor_category:
            minor_category_map_reverse = {
                "데님팬츠": "denim_pants", "숏팬츠": "short_pants", "슈트팬츠/슬랙스": "suit_slacks", "카고팬츠": "cargo_pants", "코튼팬츠": "cotton_pants", "트레이닝/조거팬츠": "training_jogger_pants", "슈트 팬츠/슬랙스": "suit_slacks",
                "긴소매": "long_sleeve", "니트/스웨터": "knit_sweater", "반소매": "short_sleeve", "셔츠/블라우스": "shirt_blouse", "슬리브리스": "sleeveless", "피케/카라": "pique_collar", "후드티": "hoodie",
                "롱스커트": "long_skirt", "미니스커트": "mini_skirt", "미디스커트": "midi_skirt",
                "맥시원피스": "maxi_onepiece", "미니원피스": "mini_onepiece", "미디원피스": "midi_onepiece"
            }
            minor_category_list = [minor_category_map_reverse.get(mnc.strip(), '') for mnc in minor_category.split(',') if mnc.strip()]
            product_minor_category = product.get('minor_category_key_en', '').lower()
            if not any(mnc_en.lower() == product_minor_category for mnc_en in minor_category_list): # Exact match for English keys
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
