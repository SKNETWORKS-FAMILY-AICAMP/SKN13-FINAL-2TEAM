from typing import List, Dict

# S3에서 로드된 원본 제품 데이터
clothing_data: List[Dict] = []

# 상품 ID를 키로 하는 상품 데이터 조회용 딕셔너리 (중앙 조회 테이블)
product_lookup_table: Dict[str, Dict] = {}

# 제품 페이지 전용 가공된 데이터 캐시 (필터링, 정렬 최적화용)
processed_clothing_data: List[Dict] = []

def get_all_products() -> List[Dict]:
    """모든 상품 데이터 반환 - clothing_data 사용"""
    return clothing_data

def get_processed_products() -> List[Dict]:
    """가공된 상품 데이터 반환 - UI 최적화용"""
    return processed_clothing_data if processed_clothing_data else clothing_data

def get_product_by_id(product_id: str) -> Dict | None:
    """중앙 조회 테이블에서 상품 ID로 단일 상품 조회"""
    return product_lookup_table.get(product_id)