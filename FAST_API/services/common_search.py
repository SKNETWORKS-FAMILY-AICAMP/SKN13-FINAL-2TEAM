"""
공통 검색 모듈
모든 Intent에서 사용하는 통합 검색 기능
"""
import os
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv
import random

from utils.safe_utils import safe_lower, safe_str

load_dotenv()

@dataclass
class SearchQuery:
    """검색 쿼리 정보"""
    colors: List[str] = None
    categories: List[str] = None
    situations: List[str] = None
    styles: List[str] = None
    keywords: List[str] = None
    locations: List[str] = None
    price_range: Tuple[int, int] = None
    brands: List[str] = None
    
    def __post_init__(self):
        # None 값들을 빈 리스트로 초기화
        for field in ['colors', 'categories', 'situations', 'styles', 'keywords', 'locations', 'brands']:
            if getattr(self, field) is None:
                setattr(self, field, [])

@dataclass
class SearchResult:
    """검색 결과"""
    products: List[Dict]
    total_count: int
    search_summary: str
    applied_filters: Dict

class CommonSearchModule:
    """공통 검색 모듈 클래스"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
        
        # 카테고리 키워드 매핑 (기존 로직에서 가져옴)
        self.category_keywords = {
            # 상의 카테고리
            "후드티": ["후드티", "후드", "후드티셔츠", "hood", "hoodie"],
            "셔츠블라우스": ["셔츠", "블라우스", "와이셔츠", "드레스셔츠", "shirt", "blouse", "dress shirt"],
            "긴소매": ["긴소매", "긴팔", "long sleeve", "longsleeve"],
            "반소매": ["반소매", "반팔", "티셔츠", "반팔티", "tshirt", "t-shirt", "tee"],
            "피케카라": ["피케", "카라", "폴로", "polo", "pique", "collar"],
            "니트스웨터": ["니트", "스웨터", "가디건", "knit", "sweater", "cardigan"],
            "슬리브리스": ["슬리브리스", "민소매", "나시", "tank", "sleeveless"],
            "애슬레저": ["애슬레저", "운동복", "스포츠", "athleisure", "activewear"],
            
            # 하의 카테고리  
            "데님팬츠": ["데님", "청바지", "진", "jeans", "jean", "denim"],
            "트레이닝조거팬츠": ["트레이닝", "조거", "운동복", "스웻팬츠", "training", "jogger", "track", "sweatpants"],
            "코튼팬츠": ["코튼", "면바지", "치노", "cotton", "chino"],
            "슈트팬츠슬랙스": ["슈트", "슬랙스", "정장바지", "정장", "suit", "slacks", "dress pants"],
            "숏팬츠": ["숏팬츠", "반바지", "shorts", "short"],
            "레깅스": ["레깅스", "leggings"]
        }
        
        self.color_keywords = {
            "빨간색": ["red", "빨간", "레드", "빨강"],
            "파란색": ["blue", "파란", "블루", "navy", "네이비", "indigo", "파랑"],
            "검은색": ["black", "검은", "블랙", "검정"],
            "흰색": ["white", "흰", "화이트", "흰색", "화이트"],
            "회색": ["gray", "grey", "회색", "그레이", "회"],
            "베이지": ["beige", "베이지", "베이지색"],
            "갈색": ["brown", "갈색", "브라운", "갈"],
            "노란색": ["yellow", "노란", "옐로", "노랑", "노란색"],
            "초록색": ["green", "초록", "그린", "녹색", "초록색"],
            "분홍색": ["pink", "분홍", "핑크", "분홍색"],
            "보라색": ["purple", "보라", "퍼플", "보라색"],
            "주황색": ["orange", "주황", "오렌지", "주황색"],
            "카키": ["khaki", "카키", "카키색"],
            "민트": ["mint", "민트", "민트색"],
            "네이비": ["navy", "네이비", "남색"],
            "와인": ["wine", "와인", "와인색", "버건디"],
            "올리브": ["olive", "올리브", "올리브색"]
        }
    
    def search_products(self, query: SearchQuery, available_products: List[Dict], 
                       context_filters: Optional[Dict] = None) -> SearchResult:
        """
        통합 상품 검색 함수
        
        Args:
            query: 검색 쿼리 정보
            available_products: 검색할 상품 목록
            context_filters: 추가 컨텍스트 기반 필터 (이전 추천과의 차별화 등)
        
        Returns:
            SearchResult: 검색 결과
        """
        print(f"=== 공통 검색 모듈 시작 ===")
        print(f"검색 조건: {query}")
        
        if not available_products:
            return SearchResult(
                products=[],
                total_count=0,
                search_summary="검색할 상품이 없습니다.",
                applied_filters={}
            )
        
        # 1. 기본 필터링
        filtered_products = self._apply_basic_filters(available_products, query)
        print(f"기본 필터링 후: {len(filtered_products)}개")
        
        # 2. 컨텍스트 기반 추가 필터링
        if context_filters:
            filtered_products = self._apply_context_filters(filtered_products, context_filters)
            print(f"컨텍스트 필터링 후: {len(filtered_products)}개")
        
        # 3. 결과 정리 및 선택
        final_products = self._select_final_products(filtered_products, query)
        
        # 4. 검색 요약 생성
        search_summary = self._generate_search_summary(query, len(final_products), len(available_products))
        
        applied_filters = {
            "colors": query.colors,
            "categories": query.categories,
            "situations": query.situations,
            "keywords": query.keywords,
            "context_applied": bool(context_filters)
        }
        
        return SearchResult(
            products=final_products,
            total_count=len(filtered_products),
            search_summary=search_summary,
            applied_filters=applied_filters
        )
    
    def _apply_basic_filters(self, products: List[Dict], query: SearchQuery) -> List[Dict]:
        """기본 필터링 적용"""
        filtered = products.copy()
        
        # 색상 필터링
        if query.colors:
            color_filtered = []
            for product in filtered:
                product_color = safe_lower(product.get("색상", ""))
                product_name = safe_lower(product.get("상품명", ""))
                
                for color in query.colors:
                    color_variants = self.color_keywords.get(color, [color])
                    if any(safe_lower(variant) in product_color or safe_lower(variant) in product_name 
                          for variant in color_variants):
                        color_filtered.append(product)
                        break
            filtered = color_filtered
            print(f"색상 필터링 적용: {query.colors} -> {len(filtered)}개")
        
        # 카테고리 필터링
        if query.categories:
            category_filtered = []
            for product in filtered:
                대분류 = safe_lower(product.get("대분류", ""))
                소분류 = safe_lower(product.get("소분류", ""))
                상품명 = safe_lower(product.get("상품명", ""))
                
                for category in query.categories:
                    category_variants = self.category_keywords.get(category, [category])
                    product_matched = False
                    
                    for variant in category_variants:
                        variant_lower = safe_lower(variant)
                        # 정확한 매칭을 위해 단어 경계 고려
                        if (self._is_word_match(variant_lower, 대분류) or 
                            self._is_word_match(variant_lower, 소분류) or 
                            self._is_word_match(variant_lower, 상품명)):
                            product_matched = True
                            break
                    
                    if product_matched:
                        category_filtered.append(product)
                        break
            filtered = category_filtered
            print(f"카테고리 필터링 적용: {query.categories} -> {len(filtered)}개")
        
        # 브랜드 필터링
        if query.brands:
            brand_filtered = []
            for product in filtered:
                brand = safe_lower(product.get("한글브랜드명", ""))
                eng_brand = safe_lower(product.get("영어브랜드명", ""))
                
                for query_brand in query.brands:
                    if (safe_lower(query_brand) in brand or 
                        safe_lower(query_brand) in eng_brand):
                        brand_filtered.append(product)
                        break
            filtered = brand_filtered
            print(f"브랜드 필터링 적용: {query.brands} -> {len(filtered)}개")
        
        # 가격 필터링
        if query.price_range:
            min_price, max_price = query.price_range
            price_filtered = []
            for product in filtered:
                price = product.get("원가", 0)
                if isinstance(price, (int, float)) and min_price <= price <= max_price:
                    price_filtered.append(product)
            filtered = price_filtered
            print(f"가격 필터링 적용: {min_price}-{max_price}원 -> {len(filtered)}개")
        
        # 키워드 필터링 (유연한 점수 기반)
        if query.keywords:
            keyword_scored = []
            for product in filtered:
                product_text = f"{safe_str(product.get('상품명', ''))} {safe_str(product.get('대분류', ''))} {safe_str(product.get('소분류', ''))}".lower()
                brand_text = f"{safe_str(product.get('한글브랜드명', ''))} {safe_str(product.get('영어브랜드명', ''))}".lower()
                
                score = 0
                matched_keywords = []
                
                for keyword in query.keywords:
                    keyword_lower = safe_lower(keyword)
                    
                    # 완전 일치 (높은 점수)
                    if keyword_lower in product_text:
                        score += 3
                        matched_keywords.append(keyword)
                    # 부분 일치 (낮은 점수)
                    elif any(part in product_text for part in keyword_lower.split() if len(part) >= 2):
                        score += 1
                        matched_keywords.append(f"{keyword}(부분)")
                    # 브랜드 일치
                    elif keyword_lower in brand_text:
                        score += 2
                        matched_keywords.append(f"{keyword}(브랜드)")
                
                # 점수가 있는 상품만 포함
                if score > 0:
                    product_copy = product.copy()
                    product_copy["_search_score"] = score
                    product_copy["_matched_keywords"] = matched_keywords
                    keyword_scored.append(product_copy)
            
            # 점수순으로 정렬
            keyword_scored.sort(key=lambda x: x.get("_search_score", 0), reverse=True)
            filtered = keyword_scored
            print(f"키워드 필터링 적용: {query.keywords} -> {len(filtered)}개 (점수 기반)")
        
        return filtered
    
    def _is_word_match(self, keyword: str, text: str) -> bool:
        """
        정확한 단어 매칭을 위한 헬퍼 함수
        부분 문자열 매칭 문제를 해결하면서도 유연성 유지
        """
        if not keyword or not text:
            return False
        
        # 기본 포함 검사
        if keyword in text:
            # 문제가 되는 케이스들을 명시적으로 제외
            problematic_cases = [
                ("셔츠", "티셔츠"),  # "셔츠"가 "티셔츠"와 매칭되는 것 방지
                ("바지", "가방"),   # 혹시 모를 경우
            ]
            
            for problem_keyword, problem_text in problematic_cases:
                if (keyword == problem_keyword and 
                    problem_text in text and 
                    text.endswith(problem_text)):
                    return False
            
            return True
        
        return False
    
    def _apply_context_filters(self, products: List[Dict], context_filters: Dict) -> List[Dict]:
        """컨텍스트 기반 추가 필터링"""
        filtered = products.copy()
        
        # 이전 추천과 다른 브랜드 우선
        if context_filters.get("exclude_brands"):
            exclude_brands = context_filters["exclude_brands"]
            different_brand_products = [
                p for p in filtered 
                if p.get("한글브랜드명", "") not in exclude_brands
            ]
            if different_brand_products:
                filtered = different_brand_products
                print(f"브랜드 차별화 필터링: {len(exclude_brands)}개 브랜드 제외 -> {len(filtered)}개")
        
        # 이전 추천과 다른 가격대 우선
        if context_filters.get("price_differentiation"):
            previous_avg_price = context_filters["price_differentiation"]
            # 이전 평균 가격과 20% 이상 차이나는 상품 우선
            differentiated_products = []
            for product in filtered:
                price = product.get("원가", 0)
                if isinstance(price, (int, float)) and price > 0:
                    price_diff_ratio = abs(price - previous_avg_price) / previous_avg_price
                    if price_diff_ratio >= 0.2:  # 20% 이상 차이
                        differentiated_products.append(product)
            
            if differentiated_products:
                filtered = differentiated_products
                print(f"가격대 차별화 필터링: 기준 {previous_avg_price}원 -> {len(filtered)}개")
        
        # 스타일 다양화
        if context_filters.get("style_diversification"):
            # 다양한 소분류의 상품들을 선택
            category_groups = {}
            for product in filtered:
                소분류 = product.get("소분류", "기타")
                if 소분류 not in category_groups:
                    category_groups[소분류] = []
                category_groups[소분류].append(product)
            
            # 각 소분류에서 일부씩 선택
            diversified_products = []
            for category, products_in_category in category_groups.items():
                max_per_category = max(1, len(products_in_category) // 2)
                selected = random.sample(products_in_category, min(max_per_category, len(products_in_category)))
                diversified_products.extend(selected)
            
            filtered = diversified_products
            print(f"스타일 다양화 필터링: {len(category_groups)}개 카테고리 -> {len(filtered)}개")
        
        return filtered
    
    def _select_final_products(self, products: List[Dict], query: SearchQuery) -> List[Dict]:
        """최종 상품 선택"""
        if not products:
            return []
        
        # 상의/하의 균형 고려
        top_products = []
        bottom_products = []
        other_products = []
        
        for product in products:
            대분류 = safe_lower(product.get("대분류", ""))
            소분류 = safe_lower(product.get("소분류", ""))
            
            if any(keyword in 대분류 or keyword in 소분류 
                  for keyword in ["상의", "탑", "top", "셔츠", "니트", "후드"]):
                top_products.append(product)
            elif any(keyword in 대분류 or keyword in 소분류 
                    for keyword in ["하의", "바텀", "bottom", "바지", "팬츠", "pants"]):
                bottom_products.append(product)
            else:
                other_products.append(product)
        
        # 최대 4개 선택 (상의 2개, 하의 2개 목표)
        final_products = []
        
        if len(top_products) >= 2 and len(bottom_products) >= 2:
            final_products.extend(random.sample(top_products, 2))
            final_products.extend(random.sample(bottom_products, 2))
        elif len(top_products) >= 2:
            final_products.extend(random.sample(top_products, 2))
            remaining_slots = 4 - len(final_products)
            if bottom_products and remaining_slots > 0:
                final_products.extend(random.sample(bottom_products, min(remaining_slots, len(bottom_products))))
        elif len(bottom_products) >= 2:
            final_products.extend(random.sample(bottom_products, 2))
            remaining_slots = 4 - len(final_products)
            if top_products and remaining_slots > 0:
                final_products.extend(random.sample(top_products, min(remaining_slots, len(top_products))))
        else:
            # 균형이 맞지 않으면 전체에서 4개 선택
            available_count = len(products)
            select_count = min(4, available_count)
            final_products = random.sample(products, select_count)
        
        # 중복 제거
        seen_ids = set()
        unique_products = []
        for product in final_products:
            product_id = product.get("상품코드", id(product))
            if product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_products.append(product)
        
        return unique_products[:4]
    
    def _generate_search_summary(self, query: SearchQuery, result_count: int, total_count: int) -> str:
        """검색 요약 생성"""
        conditions = []
        
        if query.colors:
            conditions.append(f"색상: {', '.join(query.colors)}")
        if query.categories:
            conditions.append(f"카테고리: {', '.join(query.categories)}")
        if query.situations:
            conditions.append(f"상황: {', '.join(query.situations)}")
        if query.brands:
            conditions.append(f"브랜드: {', '.join(query.brands)}")
        if query.price_range:
            min_price, max_price = query.price_range
            conditions.append(f"가격: {min_price:,}원~{max_price:,}원")
        
        condition_str = ", ".join(conditions) if conditions else "전체"
        
        if result_count == 0:
            return f"{condition_str} 조건에 맞는 상품을 찾지 못했습니다."
        else:
            return f"{condition_str} 조건으로 {total_count}개 중 {result_count}개 상품을 선별했습니다."

    def generate_search_message(self, search_result: SearchResult, query: SearchQuery) -> str:
        """검색 결과를 기반으로 사용자에게 보낼 메시지 생성"""
        if not search_result.products:
            return f"{search_result.search_summary} 다른 조건으로 검색해보세요."
        
        message = f"{search_result.search_summary}\n\n"
        
        # 상품 정보 추가
        for i, product in enumerate(search_result.products, 1):
            product_name = product.get('상품명', '상품명 없음')
            brand = product.get('한글브랜드명', '브랜드 없음')
            price = product.get('원가', 0)
            
            message += f"**{i}. {product_name}**\n"
            message += f"   📍 브랜드: {brand}\n"
            if price:
                message += f"   💰 가격: {price:,}원\n"
            message += "\n"
        
        return message
