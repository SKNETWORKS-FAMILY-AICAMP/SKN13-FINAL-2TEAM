from sqlalchemy import Column, Integer, String
from db import Base

class FAQ(Base):
    __tablename__ = "faq"

    faq_id = Column(Integer, primary_key=True, index=True)
    question = Column(String, index=True)
    answer = Column(String)
