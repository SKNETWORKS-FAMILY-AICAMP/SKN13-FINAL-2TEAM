from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_name = Column(String(255), nullable=True)  # 세션 이름 추가
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 관계 설정
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type = Column(String(20), nullable=False)  # 'user' 또는 'bot'
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 체크 제약 조건 추가
    __table_args__ = (
        CheckConstraint("message_type IN ('user', 'bot')", name="chk_message_type"),
    )

    # 관계 설정
    session = relationship("ChatSession", back_populates="messages")
