from typing import List, Dict, Any

# S3에서 로드된 원본 제품 데이터 - 챗봇과 제품 페이지에서 공통 사용
clothing_data: Dict[str, Dict[str, Any]] = {}

# 제품 페이지 전용 가공된 데이터 캐시 (필터링, 정렬 최적화용)
processed_clothing_data: List[Dict] = []

def get_all_products() -> List[Dict]:
    """모든 상품 데이터 반환 - clothing_data 사용"""
    return clothing_data

def get_processed_products() -> List[Dict]:
    """가공된 상품 데이터 반환 - UI 최적화용"""
    return processed_clothing_data if processed_clothing_data else clothing_data