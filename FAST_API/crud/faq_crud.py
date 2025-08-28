from sqlalchemy.orm import Session
from models.models_faq import FAQ
from typing import Optional

def get_all_faqs(db: Session):
    return db.query(FAQ).all()

def create_faq(db: Session, question: str, answer: str):
    db_faq = FAQ(question=question, answer=answer)
    db.add(db_faq)
    db.commit()
    db.refresh(db_faq)
    return db_faq
