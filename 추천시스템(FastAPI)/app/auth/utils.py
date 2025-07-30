from passlib.hash import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(plain_pw: str, hashed_pw: str) -> bool:
    return bcrypt.verify(plain_pw, hashed_pw)