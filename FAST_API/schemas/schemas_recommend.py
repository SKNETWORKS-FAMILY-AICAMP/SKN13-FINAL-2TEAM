
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class RecommendationRequest(BaseModel):
    """
    추천 요청을 위한 스키마
    """
    query: str = Field(..., description="사용자 쿼리")
    user_id: Optional[int] = Field(None, description="사용자 ID (로그인 시)")
    limit: int = Field(10, description="반환할 추천 수")

class RecommendationResponse(BaseModel):
    """
    추천 결과를 위한 스키마
    """
    id: int = Field(..., alias="상품코드", description="상품 ID")
    name: str = Field(..., alias="상품명", description="상품명")
    brand: str = Field(..., alias="한글브랜드명", description="브랜드명")
    price: float = Field(..., alias="가격", description="가격")
    image_url: str = Field(..., alias="이미지URL", description="이미지 URL")
    category: Optional[str] = Field(None, alias="대분류", description="카테고리")

    class Config:
        from_attributes = True
        populate_by_name = True

class RecommendationFeedbackRequest(BaseModel):
    """
    추천 피드백을 위한 스키마
    """
    recommendation_id: int = Field(..., description="추천 ID")
    feedback_rating: int = Field(..., ge=0, le=1, description="피드백 평가 (1: 좋아요, 0: 싫어요)")
    feedback_reason: Optional[str] = Field(None, description="피드백 이유 (코멘트)")

class RecommendationFeedbackResponse(BaseModel):
    """
    추천 피드백 결과를 위한 스키마
    """
    success: bool
    message: str

class RecommendationHistoryItem(BaseModel):
    """
    추천 히스토리 아이템을 위한 스키마
    """
    id: int
    item_id: int
    query: str
    reason: str
    created_at: str
    feedback_rating: Optional[int] = None
    feedback_reason: Optional[str] = None
    product_details: Optional[RecommendationResponse] = None  # 상품 상세 정보 추가

    class Config:
        from_attributes = True

class RecommendationHistoryResponse(BaseModel):
    """
    추천 히스토리 응답을 위한 스키마
    """
    history: List[RecommendationHistoryItem]
