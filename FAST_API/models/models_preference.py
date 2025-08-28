from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from db import Base

class UserPreference(Base):
    __tablename__ = "user_preferences"

    prefer_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    height = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)
    preferred_color = Column(String, nullable=True)
    preferred_style = Column(String, nullable=True)
    survey_completed = Column(Boolean, default=False, nullable=False)

    user = relationship("models.models_auth.User", back_populates="preferences")
