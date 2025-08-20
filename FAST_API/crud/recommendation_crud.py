from sqlalchemy.orm import Session
from models.recommendation import Recommendation
from typing import List, Dict

def create_recommendation(
    db: Session, 
    user_id: int, 
    item_id: int, 
    query: str, 
    reason: str
) -> Recommendation:
    """추천 결과를 데이터베이스에 저장합니다."""
    db_recommendation = Recommendation(
        user_id=user_id,
        item_id=item_id,
        query=query,
        reason=reason
    )
    db.add(db_recommendation)
    db.commit()
    db.refresh(db_recommendation)
    return db_recommendation

def create_multiple_recommendations(
    db: Session, 
    user_id: int, 
    recommendations_data: List[Dict]
) -> List[Recommendation]:
    """여러 추천 결과를 한 번에 데이터베이스에 저장합니다."""
    db_recommendations = []
    
    for rec_data in recommendations_data:
        db_recommendation = Recommendation(
            user_id=user_id,
            item_id=rec_data["item_id"],
            query=rec_data["query"],
            reason=rec_data["reason"]
        )
        db_recommendations.append(db_recommendation)
    
    db.add_all(db_recommendations)
    db.commit()
    
    for rec in db_recommendations:
        db.refresh(rec)
    
    return db_recommendations

def get_user_recommendations(
    db: Session, 
    user_id: int, 
    limit: int = 50
) -> List[Recommendation]:
    """사용자의 추천 기록을 조회합니다."""
    return db.query(Recommendation).filter(
        Recommendation.user_id == user_id
    ).order_by(Recommendation.id.desc()).limit(limit).all()

def get_recommendation_by_id(
    db: Session, 
    recommendation_id: int
) -> Recommendation:
    """ID로 추천 기록을 조회합니다."""
    return db.query(Recommendation).filter(
        Recommendation.id == recommendation_id
    ).first()

def delete_recommendation(
    db: Session, 
    recommendation_id: int, 
    user_id: int
) -> bool:
    """추천 기록을 삭제합니다."""
    recommendation = db.query(Recommendation).filter(
        Recommendation.id == recommendation_id,
        Recommendation.user_id == user_id
    ).first()
    
    if recommendation:
        db.delete(recommendation)
        db.commit()
        return True
    return False
