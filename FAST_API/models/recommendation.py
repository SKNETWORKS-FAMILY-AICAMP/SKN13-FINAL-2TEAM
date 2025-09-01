from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db import Base

class Recommendation(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, nullable=False)
    query = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    
    # 피드백 관련 컬럼 추가
    feedback_rating = Column(Integer, nullable=True)  # 1: 좋아요, 0: 싫어요, null: 없음
    feedback_reason = Column(Text, nullable=True)     # 사용자가 입력한 이유
    
    # 관계 설정 (선택사항)
    user = relationship("User", back_populates="recommendations")
