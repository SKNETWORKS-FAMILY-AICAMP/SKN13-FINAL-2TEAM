"""
브랜드 매칭 모듈
한글/영어 구분 및 RapidFuzz를 활용한 브랜드 유사도 계산
"""

from typing import List, Dict
from utils.safe_utils import safe_lower

# RapidFuzz 설치 필요: pip install rapidfuzz
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    print("⚠️ RapidFuzz가 설치되지 않았습니다. pip install rapidfuzz로 설치하세요.")


class BrandMatcher:
    """브랜드 매칭 클래스"""
    
    def __init__(self):
        pass
    
    def is_korean(self, text: str) -> bool:
        """텍스트가 한글인지 확인"""
        if not text:
            return False
        
        for char in text:
            if '가' <= char <= '힣':
                return True
        return False
    
    def is_english(self, text: str) -> bool:
        """텍스트가 영어인지 확인"""
        if not text:
            return False
        
        # 영어 알파벳이 하나라도 있으면 영어로 간주
        for char in text:
            if 'a' <= char.lower() <= 'z':
                return True
        return False
    
    def calculate_brand_similarity(self, query_brand: str, product_brand: str) -> float:
        """RapidFuzz를 사용한 브랜드 유사도 계산 - 최고 점수 반환"""
        if not query_brand or not product_brand:
            return 0.0
        
        query_lower = safe_lower(query_brand)
        product_lower = safe_lower(product_brand)
        
        # 정확한 매칭
        if query_lower == product_lower:
            return 1.0
        
        # RapidFuzz 사용
        if RAPIDFUZZ_AVAILABLE:
            # Token Sort Ratio: 단어 순서를 무시하고 유사도 계산
            token_sort_ratio = fuzz.token_sort_ratio(query_lower, product_lower) / 100.0
            
            # Partial Ratio: 부분 문자열 유사도
            partial_ratio = fuzz.partial_ratio(query_lower, product_lower) / 100.0
            
            # Token Set Ratio: 공통 단어 기반 유사도
            token_set_ratio = fuzz.token_set_ratio(query_lower, product_lower) / 100.0
            
            # 가장 높은 점수 반환
            return max(token_sort_ratio, partial_ratio, token_set_ratio)
        
        return 0.0
    
    def get_language_info(self, text: str) -> Dict[str, any]:
        """텍스트의 언어 정보 반환"""
        return {
            "text": text,
            "is_korean": self.is_korean(text),
            "is_english": self.is_english(text)
        }


# 전역 인스턴스 생성
brand_matcher = BrandMatcher()
