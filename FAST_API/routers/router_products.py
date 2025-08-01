from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_random_products, get_all_products
import re

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def process_product_data(products):
    """상품 데이터를 필터링에 필요한 형태로 가공합니다."""
    processed_products = []
    
    for product in products:
        processed_product = product.copy()
        
        # 가격 정보 처리
        price_text = product.get('가격', '')
        if price_text:
            # 할인가격 추출 (쿠폰적용가, 할인적용가 등)
            discount_match = re.search(r'할인적용가\s*(\d{1,3}(?:,\d{3})*)', price_text)
            coupon_match = re.search(r'쿠폰적용가\s*(\d{1,3}(?:,\d{3})*)', price_text)
            normal_match = re.search(r'정상가\s*(\d{1,3}(?:,\d{3})*)', price_text)
            
            if discount_match:
                processed_product['processed_price'] = int(discount_match.group(1).replace(',', ''))
            elif coupon_match:
                processed_product['processed_price'] = int(coupon_match.group(1).replace(',', ''))
            elif normal_match:
                processed_product['processed_price'] = int(normal_match.group(1).replace(',', ''))
            else:
                processed_product['processed_price'] = 0
        else:
            processed_product['processed_price'] = 0
        
        # 성별 판단 (상품명과 브랜드 기반)
        product_name = product.get('상품명', '').lower()
        brand = product.get('브랜드', '').lower()
        
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
        
        # 평점 (상품명 기반 일관된 평점 생성)
        import hashlib
        
        # 상품명을 해시하여 일관된 숫자 생성
        hash_object = hashlib.md5(product_name.encode())
        hash_hex = hash_object.hexdigest()
        hash_int = int(hash_hex[:8], 16)  # 첫 8자리를 정수로 변환
        
        # 해시값을 기반으로 평점 결정 (1.0 ~ 5.0)
        rating = 1.0 + (hash_int % 400) / 100.0  # 1.0 ~ 5.0 범위
        processed_product['평점'] = round(rating, 1)
        
        processed_products.append(processed_product)
    
    return processed_products

@router.get("/", response_class=HTMLResponse)
async def products(request: Request):
    # 모든 상품을 가져와서 처리
    all_products = get_all_products()
    processed_products = process_product_data(all_products)
    
    # 기본적으로 20개 상품만 표시 (필터링으로 더 보기 가능)
    display_products = processed_products[:20]
    
    return templates.TemplateResponse("products/category_browse.html", {
        "request": request, 
        "products": display_products
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
    brand: str = Query(None)
):
    """API endpoint for getting filtered products"""
    all_products = get_all_products()
    processed_products = process_product_data(all_products)
    
    # 필터링 적용
    filtered_products = []
    for product in processed_products:
        include_product = True
        
        if gender and product.get('성별', '') != gender:
            include_product = False
        if clothing_type and product.get('의류타입', '') != clothing_type:
            include_product = False
        if subcategory and product.get('소분류', '') != subcategory:
            include_product = False
        if min_price and product.get('processed_price', 0) < min_price:
            include_product = False
        if max_price and product.get('processed_price', 0) > max_price:
            include_product = False
        if min_rating and product.get('평점', 0) < min_rating:
            include_product = False
        if brand and brand.lower() not in product.get('브랜드', '').lower():
            include_product = False
            
        if include_product:
            filtered_products.append(product)
    
    # 페이지네이션
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_products = filtered_products[start_idx:end_idx]
    
    return {
        "products": paginated_products,
        "total": len(filtered_products),
        "page": page,
        "limit": limit,
        "has_more": end_idx < len(filtered_products)
    }