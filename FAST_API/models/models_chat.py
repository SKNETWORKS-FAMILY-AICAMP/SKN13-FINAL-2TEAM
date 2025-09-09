from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from db import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_name = Column(String(255), nullable=True)  # 세션 이름 추가
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    pending_image_path = Column(String(512), nullable=True) # 이미지 추천 대기 상태일 때, 이미지 파일의 임시 경로 저장

    # 관계 설정
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type = Column(String(20), nullable=False)  # 'user' 또는 'bot'
    text = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)  # Q/A 쌍별 요약 저장
    recommendation_id = Column(Text, nullable=True)  # 추천 결과 연결 (Integer → Text로 변경, ForeignKey 제거)
    products_data = Column(JSON, nullable=True)  # 상품 데이터를 JSON으로 저장
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 체크 제약 조건 추가
    __table_args__ = (
        CheckConstraint("message_type IN ('user', 'bot')", name="chk_message_type"),
    )

    # 관계 설정
    session = relationship("ChatSession", back_populates="messages")
    # recommendation 관계 제거 (Text 타입이므로)
