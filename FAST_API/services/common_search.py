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
    locations: List[str] = None
    price_range: Tuple[int, int] = None
    brands: List[str] = None
    
    def __post_init__(self):
        # None 값들을 빈 리스트로 초기화
        for field in ['colors', 'categories', 'situations', 'styles', 'locations', 'brands']:
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
        
        # 카테고리 키워드 매핑 (실제 데이터 구조에 맞게 업데이트)
        self.category_keywords = {
            # 대분류
            "상의": ["상의", "top", "상의류"],
            "바지": ["바지", "pants", "하의", "bottom", "하의류"],
            "스커트": ["스커트", "skirt", "치마"],
            "원피스": ["원피스", "dress", "원피스류"],
            
            # 소분류 - 상의
            "긴소매": ["긴소매", "긴팔", "long sleeve", "longsleeve", "긴소매셔츠", "긴소매니트"],
            "반소매": ["반소매", "반팔", "티셔츠", "반팔티", "tshirt", "t-shirt", "tee", "반소매셔츠"],
            "후드티": ["후드티", "후드", "후드티셔츠", "hood", "hoodie", "후드티"],
            "니트/스웨터": ["니트", "스웨터", "가디건", "knit", "sweater", "cardigan", "니트스웨터"],
            "셔츠/블라우스": ["셔츠", "블라우스", "와이셔츠", "드레스셔츠", "shirt", "blouse", "dress shirt"],
            "피케/카라": ["피케", "카라", "폴로", "polo", "pique", "collar", "피케카라"],
            "슬리브리스": ["슬리브리스", "민소매", "나시", "tank", "sleeveless", "나시티"],
            
            # 소분류 - 하의
            "데님팬츠": ["데님", "청바지", "진", "jeans", "jean", "denim", "데님팬츠"],
            "코튼팬츠": ["코튼", "면바지", "치노", "cotton", "chino", "코튼팬츠"],
            "슈트팬츠/슬랙스": ["슈트", "슬랙스", "정장바지", "정장", "suit", "slacks", "dress pants"],
            "카고팬츠": ["카고", "cargo", "카고팬츠"],
            "트레이닝/조거팬츠": ["트레이닝", "조거", "운동복", "스웻팬츠", "training", "jogger", "track", "sweatpants"],
            "숏팬츠": ["숏팬츠", "반바지", "shorts", "short"],
            
            # 소분류 - 스커트
            "롱스커트": ["롱스커트", "long skirt", "롱치마"],
            "미니스커트": ["미니스커트", "mini skirt", "미니치마"],
            "미디스커트": ["미디스커트", "midi skirt", "미디치마"],
            
            # 소분류 - 원피스
            "맥시원피스": ["맥시원피스", "maxi dress", "맥시드레스"],
            "미니원피스": ["미니원피스", "mini dress", "미니드레스"],
            "미디원피스": ["미디원피스", "midi dress", "미디드레스"]
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
        통합 상품 검색 함수 - 개선된 버전
        
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
        
        # 1. 필수 필터링 (색상, 카테고리, 브랜드, 가격)
        filtered_products = self._apply_required_filters(available_products, query)
        print(f"필수 필터링 후: {len(filtered_products)}개")
        
        # 2. 결과가 없으면 유연한 검색 시도
        if not filtered_products and (query.colors or query.categories or query.brands):
            print("필수 필터 결과 없음, 유연한 검색 시도...")
            filtered_products = self._apply_flexible_search(available_products, query)
            print(f"유연한 검색 후: {len(filtered_products)}개")
        
        # 3. 컨텍스트 기반 추가 필터링
        if context_filters and filtered_products:
            filtered_products = self._apply_context_filters(filtered_products, context_filters)
            print(f"컨텍스트 필터링 후: {len(filtered_products)}개")
        
        # 4. 결과 정리 및 선택
        final_products = self._select_final_products(filtered_products, query)
        
        # 5. 검색 요약 생성
        search_summary = self._generate_search_summary(query, len(final_products), len(available_products))
        
        applied_filters = {
            "colors": query.colors,
            "categories": query.categories,
            "situations": query.situations,
            "context_applied": bool(context_filters),
            "flexible_search": len(filtered_products) > 0 and not self._has_required_filters(filtered_products, query)
        }
        
        return SearchResult(
            products=final_products,
            total_count=len(filtered_products),
            search_summary=search_summary,
            applied_filters=applied_filters
        )
    
    def _search_by_combinations(self, query: SearchQuery, available_products: List[Dict], 
                               context_filters: Optional[Dict] = None) -> SearchResult:
        """개별 조합별로 상품 검색 (색상 + 카테고리 조합)"""
        print(f"🔍 색상 {len(query.colors)}개 + 카테고리 {len(query.categories)}개 = {len(query.colors) * len(query.categories)}개 조합 검색")
        
        all_products = []
        total_combinations = 0
        
        # 각 조합별로 검색
        for color in query.colors:
            for category in query.categories:
                total_combinations += 1
                print(f"  🔍 조합 {total_combinations}: {category} + {color}")
                
                # 개별 조합별 검색 쿼리 생성
                combination_query = SearchQuery(
                    colors=[color],
                    categories=[category],
                    situations=query.situations,
                    styles=query.styles,
                    locations=query.locations,
                    price_range=query.price_range,
                    brands=query.brands
                )
                
                # 해당 조합으로 필터링
                combination_products = self._apply_required_filters(available_products, combination_query)
                
                if combination_products:
                    # 각 조합당 최대 2개씩 추가
                    selected_products = combination_products[:2]
                    all_products.extend(selected_products)
                    print(f"    ✅ {category} + {color}: {len(selected_products)}개 상품 발견")
                else:
                    print(f"    ⚠️ {category} + {color}: 검색 결과 없음")
        
        # 중복 제거 (상품코드 기준)
        seen_ids = set()
        unique_products = []
        for product in all_products:
            product_id = product.get("상품코드", "")
            if product_id and product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_products.append(product)
        
        print(f"🎯 개별 조합별 검색 완료: 총 {len(unique_products)}개 (중복 제거 후)")
        
        # 컨텍스트 기반 추가 필터링
        if context_filters and unique_products:
            unique_products = self._apply_context_filters(unique_products, context_filters)
            print(f"컨텍스트 필터링 후: {len(unique_products)}개")
        
        # 검색 요약 생성
        search_summary = f"개별 조합별 검색으로 {len(unique_products)}개 상품을 찾았습니다."
        
        applied_filters = {
            "colors": query.colors,
            "categories": query.categories,
            "situations": query.situations,
            "combination_search": True,
            "total_combinations": total_combinations,
            "context_applied": bool(context_filters)
        }
        
        return SearchResult(
            products=unique_products,
            total_count=len(unique_products),
            search_summary=search_summary,
            applied_filters=applied_filters
        )
    
    def _apply_basic_filters(self, products: List[Dict], query: SearchQuery) -> List[Dict]:
        """기본 필터링 적용 - 개선된 버전"""
        filtered = products.copy()
        
        # 색상 필터링 (색상 필드에서만 정확한 매칭)
        if query.colors:
            color_filtered = []
            for product in filtered:
                product_color = safe_lower(product.get("색상", ""))
                
                color_matched = False
                for color in query.colors:
                    # 색상 매핑 데이터에서 변형어 가져오기
                    color_variants = self.color_keywords.get(color, [color])
                    
                    # 색상 필드에서 정확한 매칭만
                    if any(safe_lower(variant) == product_color for variant in color_variants):
                        color_matched = True
                        break
                
                if color_matched:
                    color_filtered.append(product)
            
            filtered = color_filtered
            print(f"색상 필터링 적용: {query.colors} -> {len(filtered)}개")
        
        # 카테고리 필터링 (대분류/소분류 기반)
        if query.categories:
            category_filtered = []
            for product in filtered:
                대분류 = safe_lower(product.get("대분류", ""))
                소분류 = safe_lower(product.get("소분류", ""))
                
                category_matched = False
                for category in query.categories:
                    # 카테고리 매핑 데이터에서 변형어 가져오기
                    category_variants = self.category_keywords.get(category, [category])
                    
                    # 대분류에서 정확한 매칭
                    if any(safe_lower(variant) == 대분류 for variant in category_variants):
                        category_matched = True
                        break
                    
                    # 소분류에서 정확한 매칭
                    if any(safe_lower(variant) == 소분류 for variant in category_variants):
                        category_matched = True
                        break
                    
                    # 소분류에서 부분 매칭 (긴소매셔츠 -> 긴소매 매칭)
                    if any(safe_lower(variant) in 소분류 for variant in category_variants):
                        category_matched = True
                        break
                
                if category_matched:
                    category_filtered.append(product)
            
            filtered = category_filtered
            print(f"카테고리 필터링 적용: {query.categories} -> {len(filtered)}개")
        
        # 브랜드 필터링 (브랜드가 명시적으로 지정된 경우만)
        if query.brands and len(query.brands) > 0:
            brand_filtered = []
            for product in filtered:
                한글브랜드명 = product.get("한글브랜드명", "")
                영어브랜드명 = product.get("영어브랜드명", "")
                
                brand_matched = False
                for query_brand in query.brands:
                    # 1. 정확한 매칭 시도 (기존 로직)
                    if (safe_lower(query_brand) == safe_lower(한글브랜드명) or 
                        safe_lower(query_brand) == safe_lower(영어브랜드명)):
                        brand_matched = True
                        break
                    
                    # 2. 포함 관계 시도 (기존 로직)
                    if (safe_lower(query_brand) in safe_lower(한글브랜드명) or 
                        safe_lower(query_brand) in safe_lower(영어브랜드명)):
                        brand_matched = True
                        break
                
                # 3. 기존 로직으로 매칭 안 되면 brand_matcher 사용
                if not brand_matched:
                    try:
                        from services.brand_matcher import brand_matcher
                        
                        # 한글/영어 브랜드명 모두에 대해 유사도 계산
                        max_similarity = 0.0
                        if 한글브랜드명:
                            similarity_kr = brand_matcher.calculate_brand_similarity(query_brand, 한글브랜드명)
                            max_similarity = max(max_similarity, similarity_kr)
                        
                        if 영어브랜드명:
                            similarity_en = brand_matcher.calculate_brand_similarity(query_brand, 영어브랜드명)
                            max_similarity = max(max_similarity, similarity_en)
                        
                        # 0.6 이상 유사하면 매칭으로 간주
                        if max_similarity >= 0.6:
                            brand_matched = True
                            
                            # 실제로 매칭된 브랜드명 찾기
                            if max_similarity == similarity_kr:
                                matched_brand = 한글브랜드명
                            elif max_similarity == similarity_en:
                                matched_brand = 영어브랜드명
                            else:
                                matched_brand = 한글브랜드명 or 영어브랜드명
                            
                            print(f"Brand Matcher 매칭: '{query_brand}' ↔ '{matched_brand}' (유사도: {max_similarity:.2f})")
                    
                    except ImportError:
                        print("⚠️ brand_matcher 모듈을 불러올 수 없습니다.")
                        pass
                
                if brand_matched:
                    brand_filtered.append(product)
            
            filtered = brand_filtered
            print(f"🏷️ 브랜드 필터링: {query.brands} → {len(filtered)}개")
        
        # 가격 필터링
        if query.price_range:
            min_price, max_price = query.price_range
            price_filtered = []
            for product in filtered:
                price = product.get("원가", 0)
                if isinstance(price, (int, float)) and min_price <= price <= max_price:
                    price_filtered.append(product)
            filtered = price_filtered
            print(f"💰 가격 필터링: {min_price:,}-{max_price:,}원 → {len(filtered)}개")
        
        return filtered
    
    def _apply_required_filters(self, products: List[Dict], query: SearchQuery) -> List[Dict]:
        """필수 필터 적용 (색상, 카테고리, 브랜드, 가격)"""
        filtered = products.copy()
        
        # 색상 필터링 (색상 필드에서만 정확한 매칭)
        if query.colors:
            color_filtered = []
            for product in filtered:
                product_color = safe_lower(product.get("색상", ""))
                
                color_matched = False
                for color in query.colors:
                    color_variants = self.color_keywords.get(color, [color])
                    
                    # 색상 필드에서 정확한 매칭만
                    if any(safe_lower(variant) == product_color for variant in color_variants):
                        color_matched = True
                        break
                
                if color_matched:
                    color_filtered.append(product)
            
            filtered = color_filtered
            print(f"🎨 색상 필터링: {query.colors} → {len(filtered)}개")
        
        # 카테고리 필터링 (대분류/소분류 기반)
        if query.categories:
            category_filtered = []
            for product in filtered:
                대분류 = safe_lower(product.get("대분류", ""))
                소분류 = safe_lower(product.get("소분류", ""))
                
                category_matched = False
                for category in query.categories:
                    # 카테고리 매핑 없이 원본 카테고리 그대로 사용
                    category_variants = [category]
                    
                    # 대분류에서 정확한 매칭
                    if any(safe_lower(variant) == 대분류 for variant in category_variants):
                        category_matched = True
                        break
                    
                    # 소분류에서 정확한 매칭
                    if any(safe_lower(variant) == 소분류 for variant in category_variants):
                        category_matched = True
                        break
                    
                    # 소분류에서 부분 매칭 (긴소매셔츠 -> 긴소매 매칭)
                    if any(safe_lower(variant) in 소분류 for variant in category_variants):
                        category_matched = True
                        break
                
                if category_matched:
                    category_filtered.append(product)
            
            filtered = category_filtered
            print(f"📁 카테고리 필터링: {query.categories} → {len(filtered)}개")
        
        # 브랜드 필터링 (브랜드가 명시적으로 지정된 경우만)
        if query.brands and len(query.brands) > 0:
            brand_filtered = []
            for query_brand in query.brands:
                # 1. 정확한 매칭 시도 (기존 로직)
                exact_matches = []
                fuzzy_matches = []
                
                for product in filtered:
                    한글브랜드명 = product.get("한글브랜드명", "")
                    영어브랜드명 = product.get("영어브랜드명", "")
                    
                    # 정확한 매칭 확인
                    if (safe_lower(query_brand) == safe_lower(한글브랜드명) or 
                        safe_lower(query_brand) == safe_lower(영어브랜드명)):
                        exact_matches.append(product)
                        continue
                
                # 2. 정확한 매칭이 있으면 그것만 사용
                if exact_matches:
                    brand_filtered.extend(exact_matches)
                    print(f"정확한 브랜드 매칭: '{query_brand}' -> {len(exact_matches)}개")
                    continue
                
                # 3. 정확한 매칭이 없으면 모든 브랜드와 유사도 계산 후 최고 점수 선택
                try:
                    from services.brand_matcher import brand_matcher
                    
                    best_matches = []
                    best_similarity = 0.0
                    
                    for product in filtered:
                        한글브랜드명 = product.get("한글브랜드명", "")
                        영어브랜드명 = product.get("영어브랜드명", "")
                        
                        # 한글/영어 브랜드명 모두에 대해 유사도 계산
                        max_similarity = 0.0
                        if 한글브랜드명:
                            similarity_kr = brand_matcher.calculate_brand_similarity(query_brand, 한글브랜드명)
                            max_similarity = max(max_similarity, similarity_kr)
                        
                        if 영어브랜드명:
                            similarity_en = brand_matcher.calculate_brand_similarity(query_brand, 영어브랜드명)
                            max_similarity = max(max_similarity, similarity_en)
                        
                        # 최고 유사도 업데이트
                        if max_similarity > best_similarity:
                            best_similarity = max_similarity
                            best_matches = [product]
                        elif max_similarity == best_similarity:
                            best_matches.append(product)
                    
                    # 0.6 이상 유사하면 최고 점수 브랜드들 매칭
                    if best_similarity >= 0.6:
                        brand_filtered.extend(best_matches)
                        
                        # 실제로 매칭된 브랜드명 찾기
                        matched_brand = ""
                        for product in best_matches:
                            한글브랜드명 = product.get("한글브랜드명", "")
                            영어브랜드명 = product.get("영어브랜드명", "")
                            
                            # 한글/영어 브랜드명과 유사도 계산하여 매칭된 브랜드 찾기
                            if 한글브랜드명:
                                similarity_kr = brand_matcher.calculate_brand_similarity(query_brand, 한글브랜드명)
                                if abs(similarity_kr - best_similarity) < 0.01:  # 유사도가 거의 같으면
                                    matched_brand = 한글브랜드명
                                    break
                            
                            if 영어브랜드명:
                                similarity_en = brand_matcher.calculate_brand_similarity(query_brand, 영어브랜드명)
                                if abs(similarity_en - best_similarity) < 0.01:  # 유사도가 거의 같으면
                                    matched_brand = 영어브랜드명
                                    break
                        
                        # 매칭된 브랜드가 없으면 첫 번째 제품의 브랜드 표시
                        if not matched_brand:
                            matched_brand = best_matches[0].get('한글브랜드명') or best_matches[0].get('영어브랜드명')
                        
                        print(f"Brand Matcher 최고 유사도 매칭: '{query_brand}' ↔ '{matched_brand}' (유사도: {best_similarity:.2f}) -> {len(best_matches)}개")
                    else:
                        print(f"브랜드 매칭 실패: '{query_brand}' (최고 유사도: {best_similarity:.2f})")
                
                except ImportError:
                    print("⚠️ brand_matcher 모듈을 불러올 수 없습니다.")
                    pass
            
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
        if query.brands and len(query.brands) > 0:
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
    

    

    
    def _apply_flexible_search(self, products: List[Dict], query: SearchQuery) -> List[Dict]:
        """유연한 검색 (필수 필터가 너무 제한적일 때)"""
        flexible_products = []
        
        for product in products:
            product_color = safe_lower(product.get("색상", ""))
            product_name = safe_lower(product.get("상품명", ""))
            대분류 = safe_lower(product.get("대분류", ""))
            소분류 = safe_lower(product.get("소분류", ""))
            한글브랜드명 = safe_lower(product.get("한글브랜드명", ""))
            영어브랜드명 = safe_lower(product.get("영어브랜드명", ""))
            
            # 색상 유연 검색 (색상 필드에서만)
            color_flexible = True
            if query.colors:
                color_found = False
                for color in query.colors:
                    color_variants = self.color_keywords.get(color, [color])
                    if any(safe_lower(variant) == product_color for variant in color_variants):
                        color_found = True
                        break
                color_flexible = color_found
            
            # 카테고리 유연 검색 (대분류만)
            category_flexible = True
            if query.categories:
                category_found = False
                for category in query.categories:
                    category_variants = self.category_keywords.get(category, [category])
                    if any(safe_lower(variant) == 대분류 for variant in category_variants):
                        category_found = True
                        break
                category_flexible = category_found
            
            # 브랜드 유연 검색 (부분 매칭)
            brand_flexible = True
            if query.brands and len(query.brands) > 0:
                brand_found = False
                for query_brand in query.brands:
                    query_brand_lower = safe_lower(query_brand)
                    if (query_brand_lower in 한글브랜드명 or query_brand_lower in 영어브랜드명):
                        brand_found = True
                        break
                brand_flexible = brand_found
            
            # 모든 조건이 유연하게 만족되면 포함
            if color_flexible and category_flexible and brand_flexible:
                flexible_products.append(product)
        
        return flexible_products[:20]  # 최대 20개만 반환
    
    def _has_required_filters(self, products: List[Dict], query: SearchQuery) -> bool:
        """필수 필터가 적용되었는지 확인"""
        if not products:
            return False
        
        # 샘플 상품에서 필터 조건 확인
        sample_product = products[0]
        
        if query.colors:
            product_color = safe_lower(sample_product.get("색상", ""))
            color_matched = any(
                any(safe_lower(variant) == product_color for variant in self.color_keywords.get(color, [color]))
                for color in query.colors
            )
            if not color_matched:
                return False
        
        if query.categories:
            대분류 = safe_lower(sample_product.get("대분류", ""))
            소분류 = safe_lower(sample_product.get("소분류", ""))
            category_matched = any(
                any(safe_lower(variant) in [대분류, 소분류] for variant in self.category_keywords.get(category, [category]))
                for category in query.categories
            )
            if not category_matched:
                return False
        
        return True
    

