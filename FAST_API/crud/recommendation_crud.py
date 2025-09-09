from sqlalchemy.orm import Session
from models.recommendation import Recommendation
from typing import List, Dict
import json

def create_recommendation(
    db: Session, 
    user_id: int, 
    item_id: int,  # item_ids → item_id로 되돌림
    query: str, 
    reason: str
) -> Recommendation:
    """추천 결과를 데이터베이스에 저장합니다."""
    db_recommendation = Recommendation(
        user_id=user_id,
        item_id=item_id,  # item_ids → item_id로 되돌림
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
    
    # 중복 체크를 위한 기존 추천 상품 ID 조회 (더 많은 기록 조회)
    existing_item_ids = set()
    existing_recommendations = db.query(Recommendation).filter(
        Recommendation.user_id == user_id
    ).all()
    
    for existing_rec in existing_recommendations:
        existing_item_ids.add(existing_rec.item_id)
    
    print(f"🔍 사용자 {user_id}의 기존 추천 상품 수: {len(existing_item_ids)}")
    
    # 중복되지 않는 추천만 필터링
    unique_recommendations_data = []
    duplicate_count = 0
    
    for rec_data in recommendations_data:
        if rec_data["item_id"] not in existing_item_ids:
            unique_recommendations_data.append(rec_data)
            existing_item_ids.add(rec_data["item_id"])  # 중복 방지를 위해 추가
        else:
            duplicate_count += 1
            print(f"ℹ️ 상품 {rec_data['item_id']}는 이미 추천되어 저장하지 않습니다.")
    
    if duplicate_count > 0:
        print(f"⚠️ 중복 상품 {duplicate_count}개는 저장하지 않습니다.")
    
    if not unique_recommendations_data:
        print("⚠️ 모든 추천 상품이 이미 존재합니다.")
        return []
    
    # 중복되지 않는 추천만 저장
    for rec_data in unique_recommendations_data:
        db_recommendation = Recommendation(
            user_id=user_id,
            item_id=rec_data["item_id"],  # item_ids → item_id로 되돌림
            query=rec_data["query"],
            reason=rec_data["reason"]
        )
        db_recommendations.append(db_recommendation)
    
    if db_recommendations:
        db.add_all(db_recommendations)
        db.commit()
        
        for rec in db_recommendations:
            db.refresh(rec)
        
        print(f"✅ 중복 제거 후 {len(db_recommendations)}개 추천을 저장했습니다.")
    
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

# 피드백 관련 함수들
def update_recommendation_feedback(
    db: Session,
    recommendation_id: int,
    user_id: int,
    feedback_rating: int,  # 1: 좋아요, 0: 싫어요
    feedback_reason: str = None
) -> bool:
    """추천에 대한 피드백을 업데이트합니다."""
    recommendation = db.query(Recommendation).filter(
        Recommendation.id == recommendation_id,
        Recommendation.user_id == user_id
    ).first()
    
    if recommendation:
        # 코멘트가 있는 경우와 일반 피드백을 구분하여 처리
        if feedback_reason and feedback_reason.strip():  # 코멘트가 있는 경우
            # 코멘트는 기존 코멘트에 추가 (덮어쓰지 않음)
            if recommendation.feedback_reason:
                # 기존 코멘트가 있으면 새 줄로 추가
                recommendation.feedback_reason = recommendation.feedback_reason + "\n---\n" + feedback_reason
            else:
                # 기존 코멘트가 없으면 새로 저장
                recommendation.feedback_reason = feedback_reason
            db.commit()
            return True
        else:  # 일반 피드백만 있는 경우
            # 이미 피드백이 있는지 확인
            if recommendation.feedback_rating is not None:
                # 기존 피드백이 있으면 업데이트하지 않고 True 반환 (중복 방지)
                return True
            
            recommendation.feedback_rating = feedback_rating
            db.commit()
            return True
    else:
        return False

def get_recommendation_feedback_stats(
    db: Session,
    user_id: int = None
) -> Dict:
    """피드백 통계를 조회합니다."""
    query = db.query(Recommendation)
    
    if user_id:
        query = query.filter(Recommendation.user_id == user_id)
    
    total_recommendations = query.count()
    positive_feedback = query.filter(Recommendation.feedback_rating == 1).count()
    negative_feedback = query.filter(Recommendation.feedback_rating == 0).count()
    no_feedback = query.filter(Recommendation.feedback_rating.is_(None)).count()
    
    return {
        "total": total_recommendations,
        "positive": positive_feedback,
        "negative": negative_feedback,
        "no_feedback": no_feedback,
        "satisfaction_rate": (positive_feedback / (positive_feedback + negative_feedback) * 100) if (positive_feedback + negative_feedback) > 0 else 0
    }
