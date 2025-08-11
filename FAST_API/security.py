# 패스워드 해시 기능을 제거하고 일반 패스워드로 처리
def hash_password(plain_password: str) -> str:
    return plain_password


def verify_password(plain_password: str, stored_password: str) -> bool:
    return plain_password == stored_password


