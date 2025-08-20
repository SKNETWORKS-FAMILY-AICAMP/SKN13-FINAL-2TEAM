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
    
    # 관계 설정 (선택사항)
    user = relationship("User", back_populates="recommendations")
