from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from models.models_auth import User
from models.models_mypage import UserPreference
from models.models_jjim import Jjim


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, username: str, hashed_password: str) -> User:
    user = User(username=username, hashed_password=hashed_password, email="", gender=None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def upsert_user_preference(
    db: Session,
    user_id: int,
    *,
    height: Optional[int] = None,
    weight: Optional[int] = None,
    preferred_color: Optional[str] = None,
    preferred_style: Optional[str] = None,
) -> UserPreference:
    stmt = select(UserPreference).where(UserPreference.user_id == user_id)
    pref = db.execute(stmt).scalar_one_or_none()
    if pref is None:
        pref = UserPreference(
            user_id=user_id,
            height=height,
            weight=weight,
            preferred_color=preferred_color,
            preferred_style=preferred_style,
        )
        db.add(pref)
    else:
        pref.height = height
        pref.weight = weight
        pref.preferred_color = preferred_color
        pref.preferred_style = preferred_style

    db.commit()
    db.refresh(pref)
    return pref


def get_preference_by_user_id(db: Session, user_id: int) -> Optional[UserPreference]:
    stmt = select(UserPreference).where(UserPreference.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def add_jjim(db: Session, user_id: int, product_id: str) -> Jjim:
    # 중복 방지
    stmt = select(Jjim).where(Jjim.user_id == user_id, Jjim.product_id == product_id)
    exists = db.execute(stmt).scalar_one_or_none()
    if exists:
        return exists
    rec = Jjim(user_id=user_id, product_id=str(product_id))
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def remove_jjim(db: Session, user_id: int, product_id: str) -> bool:
    stmt = select(Jjim).where(Jjim.user_id == user_id, Jjim.product_id == product_id)
    rec = db.execute(stmt).scalar_one_or_none()
    if not rec:
        return False
    db.delete(rec)
    db.commit()
    return True


def list_jjim_product_ids(db: Session, user_id: int) -> list[str]:
    rows = db.execute(select(Jjim.product_id).where(Jjim.user_id == user_id)).all()
    return [r[0] for r in rows]


def remove_jjim_bulk(db: Session, user_id: int, product_ids: list[str]) -> int:
    if not product_ids:
        return 0
    stmt = delete(Jjim).where(Jjim.user_id == user_id, Jjim.product_id.in_([str(pid) for pid in product_ids]))
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


