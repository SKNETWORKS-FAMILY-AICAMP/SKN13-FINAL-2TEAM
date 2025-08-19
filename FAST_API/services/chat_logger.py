from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class RecommendationItem:
    category: str
    color: str
    type: str
    reason: str
    matched_product: Optional[Dict] = None
    search_query_used: str = ""

def prepare_chat_log_data(matched_items: List[RecommendationItem], balanced_products: List[Dict]) -> Dict:
    """챗 로그용 메타데이터를 준비합니다."""
    
    chat_log_data = {
        "matched_items": [],
        "final_products": []
    }
    
    # 매칭된 아이템 정보 (실제로 매칭된 상품이 있는 것만)
    for item in matched_items:
        if item.matched_product:  # 매칭된 상품이 있는 경우만 포함
            item_data = {
                "category": item.category,
                "color": item.color,
                "type": item.type,
                "reason": item.reason,
                "search_query_used": item.search_query_used,
                "matched_product": {
                    "상품코드": item.matched_product.get("상품코드", ""),
                    "상품명": item.matched_product.get("상품명", ""),
                    "한글브랜드명": item.matched_product.get("한글브랜드명", ""),
                    "matched_price": item.matched_product.get('원가', 0),
                    "색상": item.matched_product.get("색상", ""),
                    "대분류": item.matched_product.get("대분류", ""),
                    "소분류": item.matched_product.get("소분류", "")
                }
            }
            
            chat_log_data["matched_items"].append(item_data)
    
    # 최종 추천 상품 정보
    for product in balanced_products:
        product_data = {
            "상품코드": product.get("상품코드", ""),
            "상품명": product.get("상품명", ""),
            "한글브랜드명": product.get("한글브랜드명", ""),
            "가격": product.get('원가', 0),
            "색상": product.get("색상", ""),
            "대분류": product.get("대분류", ""),
            "소분류": product.get("소분류", ""),
            "이미지URL": product.get("이미지URL", "")
        }
        chat_log_data["final_products"].append(product_data)
    
    return chat_log_data
