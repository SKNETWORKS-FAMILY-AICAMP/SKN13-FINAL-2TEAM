import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# 환경변수 로드
load_dotenv()


def _build_database_url() -> str:
    """환경변수에서 PostgreSQL 연결 URL을 구성합니다."""
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "1234")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "musinsa")
    return f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


DATABASE_URL: str = os.getenv("DATABASE_URL", _build_database_url())

# SQLAlchemy 기본 객체들
# Lazy initialization to avoid connection errors on import
_engine = None
_SessionLocal = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine

def get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)
    return _SessionLocal

# Keep Base for model definitions
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """요청 스코프 DB 세션을 제공합니다."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """모델을 임포트하고 테이블을 생성합니다."""
    # 모델 임포트는 이 함수 내부에서 수행하여 순환 임포트를 방지합니다.
    from models import models_auth  # noqa: F401
    from models import models_mypage  # noqa: F401
    from models import models_jjim  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    _migrate_users_table()


def bootstrap_admin() -> None:
    """환경변수에 따라 최초 관리자 계정을 보장합니다.
    ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD
    """
    from sqlalchemy import select
    from models.models_auth import User
    from security import hash_password

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_username or not admin_email or not admin_password:
        return

    db = get_session_local()()
    try:
        exists = db.execute(select(User).where((User.username == admin_username) | (User.email == admin_email))).scalar_one_or_none()
        if exists:
            return
        user = User(
            username=admin_username,
            email=admin_email,
            password=hash_password(admin_password),
            gender=None,
            role="admin",
        )
        db.add(user)
        db.commit()
    finally:
        db.close()


def _migrate_users_table() -> None:
    """기존 users 테이블에 필요한 컬럼/인덱스를 추가합니다."""
    from sqlalchemy import text

    with get_engine().begin() as conn:
        # 존재 컬럼 조회
        cols = conn.execute(
            text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' AND table_schema = 'public'
            """)
        ).scalars().all()
        cols_set = set(cols)

        # hashed_password를 password로 변경
        if 'hashed_password' in cols_set and 'password' not in cols_set:
            conn.execute(text("ALTER TABLE public.users RENAME COLUMN hashed_password TO password"))

        # email 추가
        if 'email' not in cols_set:
            conn.execute(text("ALTER TABLE public.users ADD COLUMN email VARCHAR(255)"))
            # 유니크 인덱스 (NULL 허용; 중복 방지)
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON public.users (email)"))

        # gender 추가
        if 'gender' not in cols_set:
            conn.execute(text("ALTER TABLE public.users ADD COLUMN gender VARCHAR(20)"))

        # role 추가 (기본 'user', NOT NULL)
        if 'role' not in cols_set:
            conn.execute(text("ALTER TABLE public.users ADD COLUMN role VARCHAR(20)"))
            conn.execute(text("UPDATE public.users SET role = 'user' WHERE role IS NULL"))
            conn.execute(text("ALTER TABLE public.users ALTER COLUMN role SET NOT NULL"))
        else:
            # 이미 존재하지만 NULL 허용 상태일 수 있으므로 기본 보정
            conn.execute(text("UPDATE public.users SET role = 'user' WHERE role IS NULL"))


