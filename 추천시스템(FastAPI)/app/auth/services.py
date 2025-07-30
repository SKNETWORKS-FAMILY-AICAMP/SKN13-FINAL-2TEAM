# Business logic for auth

from . import crud, utils
from sqlalchemy.orm import Session
from .schemas import UserCreate

def register_user(user_data: UserCreate, db: Session):
    if crud.get_user_by_email(db, user_data.email):
        raise ValueError("이미 등록된 이메일입니다.")
    hashed_pw = utils.hash_password(user_data.password)
    user_data.password = hashed_pw
    return crud.create_user(db, user_data)