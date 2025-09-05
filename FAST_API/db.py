import os
from typing import Generator
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# 환경변수는 main.py에서 로드됨


def _build_database_url() -> str:
    """환경변수에서 PostgreSQL 연결 URL을 구성합니다."""
    db_user = os.getenv("DB_USER", "postgres")
    db_password = quote_plus(os.getenv("DB_PASSWORD", "1234")) # 비밀번호 URL 인코딩
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "musinsa")
    return f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


DATABASE_URL: str = os.getenv("DATABASE_URL", _build_database_url())

# SQLAlchemy 기본 객체들
engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"}, pool_pre_ping=True) # SSL 강제
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """요청 스코프 DB 세션을 제공합니다."""
    db = SessionLocal()
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
    from models import models_chat  # noqa: F401
    from models import recommendation  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_users_table()
    _migrate_chat_tables()


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

    db = SessionLocal()
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

    with engine.begin() as conn:
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

def _migrate_chat_tables() -> None:
    """챗봇 테이블에 필요한 컬럼을 추가합니다."""
    from sqlalchemy import text

    with engine.begin() as conn:
        # chat_session 테이블 컬럼 조회
        try:
            session_cols = conn.execute(
                text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'chat_session' AND table_schema = 'public'
                """)
            ).scalars().all()
            session_cols_set = set(session_cols)

            # session_name 컬럼 추가
            if 'session_name' not in session_cols_set:
                conn.execute(text("ALTER TABLE public.chat_session ADD COLUMN session_name VARCHAR(255)"))

            # updated_at 컬럼 추가
            if 'updated_at' not in session_cols_set:
                conn.execute(text("ALTER TABLE public.chat_session ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
                conn.execute(text("UPDATE public.chat_session SET updated_at = created_at WHERE updated_at IS NULL"))

        except Exception as e:
            print(f"챗봇 테이블 마이그레이션 중 오류 (테이블이 없을 수 있음): {e}")

        # chat_messages 테이블 컬럼 조회 및 수정
        try:
            message_cols = conn.execute(
                text("""
                    SELECT column_name, is_nullable 
                    FROM information_schema.columns
                    WHERE table_name = 'chat_messages' AND table_schema = 'public'
                """)
            ).fetchall()
            message_cols_dict = {col[0]: col[1] for col in message_cols}

            # summary 컬럼이 존재하고 NOT NULL이면 NULL 허용으로 변경
            if 'summary' in message_cols_dict and message_cols_dict['summary'] == 'NO':
                conn.execute(text("ALTER TABLE public.chat_messages ALTER COLUMN summary DROP NOT NULL"))
                print("✅ chat_messages 테이블의 summary 컬럼을 NULL 허용으로 변경 완료")

        except Exception as e:
            print(f"chat_messages 컬럼 수정 중 오류: {e}")

        # chat_messages 테이블에 recommendation_id 컬럼 추가
        try:
            # 기존 컬럼이 INTEGER이면 TEXT로 변경
            existing_cols = conn.execute(
                text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns
                    WHERE table_name = 'chat_messages' AND table_schema = 'public'
                      AND column_name = 'recommendation_id'
                """)
            ).fetchall()
            
            if existing_cols:
                if existing_cols[0][1] == 'integer':
                    # Foreign Key 제약 조건 제거
                    try:
                        conn.execute(text("ALTER TABLE public.chat_messages DROP CONSTRAINT IF EXISTS chat_messages_recommendation_id_fkey"))
                        print("✅ chat_messages 테이블의 Foreign Key 제약 조건 제거 완료")
                    except Exception as e:
                        print(f"Foreign Key 제약 조건 제거 중 오류 (이미 제거되었을 수 있음): {e}")
                    
                    # 기존 컬럼을 TEXT로 변경
                    conn.execute(text("ALTER TABLE public.chat_messages ALTER COLUMN recommendation_id TYPE TEXT"))
                    print("✅ chat_messages 테이블의 recommendation_id 컬럼을 TEXT로 변경 완료")
                else:
                    print("✅ chat_messages 테이블의 recommendation_id 컬럼이 이미 TEXT 타입입니다")
            else:
                # 컬럼이 없으면 새로 추가
                conn.execute(text("ALTER TABLE public.chat_messages ADD COLUMN recommendation_id TEXT"))
                print("✅ chat_messages 테이블에 recommendation_id 컬럼 추가 완료")
        except Exception as e:
            print(f"recommendation_id 컬럼 수정 중 오류: {e}")

        # chat_messages 테이블에 products_data 컬럼 추가
        try:
            conn.execute(text("ALTER TABLE public.chat_messages ADD COLUMN IF NOT EXISTS products_data JSONB"))
            print("✅ chat_messages 테이블에 products_data 컬럼 추가 완료")
        except Exception as e:
            print(f"products_data 컬럼 추가 중 오류: {e}")

        # chat_messages 테이블 제약 조건 확인 및 추가
        try:
            # 기존 제약 조건 확인 (올바른 뷰 조합 사용)
            existing_constraints = conn.execute(
                text("""
                    SELECT c.constraint_name
                    FROM information_schema.check_constraints c
                    JOIN information_schema.table_constraints t
                      ON c.constraint_name = t.constraint_name
                     AND c.constraint_schema = t.constraint_schema
                    WHERE t.table_schema = 'public'
                      AND t.table_name = 'chat_messages'
                      AND c.constraint_name = 'chk_message_type'
                """)
            ).scalars().all()
            
            # 기존 제약 조건이 있으면 삭제
            if existing_constraints:
                conn.execute(text("ALTER TABLE public.chat_messages DROP CONSTRAINT IF EXISTS chk_message_type"))
                print("✅ 기존 chk_message_type 제약 조건 삭제 완료")
            
            # 새로운 제약 조건 추가
            conn.execute(text("ALTER TABLE public.chat_messages ADD CONSTRAINT chk_message_type CHECK (message_type IN ('user', 'bot'))"))
            print("✅ chat_messages 테이블에 message_type 체크 제약 조건 추가 완료")

        except Exception as e:
            print(f"chat_messages 제약 조건 마이그레이션 중 오류: {e}")
            # 오류가 발생하면 별도의 트랜잭션으로 재시도
            try:
                with engine.begin() as conn2:
                    conn2.execute(text("ALTER TABLE public.chat_messages DROP CONSTRAINT IF EXISTS chk_message_type"))
                    conn2.execute(text("ALTER TABLE public.chat_messages ADD CONSTRAINT chk_message_type CHECK (message_type IN ('user', 'bot'))"))
                    print("✅ 제약 조건 재설정 완료 (새 트랜잭션)")
            except Exception as e2:
                print(f"제약 조건 재설정 실패: {e2}")