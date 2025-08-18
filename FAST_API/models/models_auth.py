from sqlalchemy import Column, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import relationship
from db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    gender = Column(String(20), nullable=True)
    role = Column(String(20), nullable=False, server_default=text("'user'"))

    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

