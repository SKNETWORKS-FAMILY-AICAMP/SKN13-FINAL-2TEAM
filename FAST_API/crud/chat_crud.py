from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from datetime import datetime, timedelta

from models.models_chat import ChatSession, ChatMessage
from models.models_auth import User


def create_chat_session(db: Session, user_id: int, session_name: Optional[str] = None) -> ChatSession:
    """새로운 챗봇 세션을 생성합니다."""
    if not session_name:
        # 기본 세션 이름 생성 (현재 시간 기반)
        session_name = f"{datetime.now().strftime('%m월 %d일 %H:%M')}"
    
    session = ChatSession(sender_id=user_id, session_name=session_name)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_latest_chat_session(db: Session, user_id: int, hours: int = 24) -> Optional[ChatSession]:
    """사용자의 최근 챗봇 세션을 가져옵니다 (지정된 시간 내)."""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    stmt = select(ChatSession).where(
        ChatSession.sender_id == user_id,
        ChatSession.created_at >= cutoff_time
    ).order_by(desc(ChatSession.created_at)).limit(1)
    
    return db.execute(stmt).scalar_one_or_none()


def get_user_chat_sessions(db: Session, user_id: int, limit: int = 20) -> List[ChatSession]:
    """사용자의 모든 챗봇 세션을 가져옵니다."""
    stmt = select(ChatSession).where(
        ChatSession.sender_id == user_id
    ).order_by(desc(ChatSession.updated_at)).limit(limit)
    
    return list(db.execute(stmt).scalars().all())


def get_chat_session_by_id(db: Session, session_id: int, user_id: int) -> Optional[ChatSession]:
    """특정 세션을 가져옵니다 (사용자 권한 확인)."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.sender_id == user_id
    )
    return db.execute(stmt).scalar_one_or_none()


def update_session_name(db: Session, session_id: int, user_id: int, new_name: str) -> bool:
    """세션 이름을 업데이트합니다."""
    session = get_chat_session_by_id(db, session_id, user_id)
    if session:
        session.session_name = new_name
        session.updated_at = datetime.utcnow()
        db.commit()
        return True
    return False


def delete_chat_session(db: Session, session_id: int, user_id: int) -> bool:
    """챗봇 세션을 삭제합니다."""
    session = get_chat_session_by_id(db, session_id, user_id)
    if session:
        db.delete(session)
        db.commit()
        return True
    return False


def create_chat_message(db: Session, session_id: int, message_type: str, text: str) -> ChatMessage:
    """챗봇 메시지를 생성합니다."""
    message = ChatMessage(
        session_id=session_id,
        message_type=message_type,
        text=text
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    # 세션의 updated_at 업데이트
    session = db.get(ChatSession, session_id)
    if session:
        session.updated_at = datetime.utcnow()
        db.commit()
    
    return message


def get_chat_messages(db: Session, session_id: int, limit: int = 10) -> List[ChatMessage]:
    """특정 세션의 메시지들을 가져옵니다."""
    stmt = select(ChatMessage).where(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).limit(limit)
    
    return list(db.execute(stmt).scalars().all())


def get_user_chat_history(db: Session, user_id: int, limit: int = 20) -> List[ChatMessage]:
    """사용자의 최근 챗봇 대화 기록을 가져옵니다."""
    stmt = select(ChatMessage).join(ChatSession).where(
        ChatSession.sender_id == user_id
    ).order_by(desc(ChatMessage.created_at)).limit(limit)
    
    return list(db.execute(stmt).scalars().all())


def get_conversation_context(db: Session, user_id: int, max_messages: int = 5) -> str:
    """사용자의 최근 대화 컨텍스트를 문자열로 반환합니다."""
    messages = get_user_chat_history(db, user_id, max_messages)
    
    if not messages:
        return ""
    
    # 최신 메시지부터 역순으로 정렬
    messages.reverse()
    
    context = []
    for msg in messages:
        role = "사용자" if msg.message_type == "user" else "챗봇"
        context.append(f"{role}: {msg.text}")
    
    return "\n".join(context)


def get_session_messages(db: Session, session_id: int, user_id: int) -> List[dict]:
    """특정 세션의 메시지들을 가져옵니다 (사용자 권한 확인)."""
    session = get_chat_session_by_id(db, session_id, user_id)
    if not session:
        return []
    
    messages = get_chat_messages(db, session_id, limit=100)
    
    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "type": msg.message_type,
            "text": msg.text,
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        })
    
    return result


def get_chat_history_for_llm(db: Session, session_id: int, user_id: int, limit: int = 6) -> List[Dict]:
    """LLM용 대화 기록을 가져옵니다 (최근 3쌍)."""
    session = get_chat_session_by_id(db, session_id, user_id)
    if not session:
        return []
    
    messages = get_chat_messages(db, session_id, limit=limit)
    
    result = []
    for msg in messages:
        result.append({
            "role": "user" if msg.message_type == "user" else "assistant",
            "content": msg.text
        })
    
    return result
