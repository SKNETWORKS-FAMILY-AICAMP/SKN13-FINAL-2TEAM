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


def create_chat_message(db: Session, session_id: int, message_type: str, text: str, summary: Optional[str] = None) -> ChatMessage:
    """챗봇 메시지를 생성합니다."""
    try:
        message = ChatMessage(
            session_id=session_id,
            message_type=message_type,
            text=text,
            summary=summary
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
    except Exception as e:
        db.rollback()
        # summary가 None일 때 문제가 발생하면 빈 문자열로 재시도
        if summary is None and "null value" in str(e).lower():
            print(f"Warning: summary 컬럼에 NULL 허용되지 않음. 빈 문자열로 재시도: {e}")
            message = ChatMessage(
                session_id=session_id,
                message_type=message_type,
                text=text,
                summary=""
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
        else:
            raise


def update_message_summary(db: Session, message_id: int, summary: str) -> bool:
    """메시지의 요약을 업데이트합니다."""
    message = db.get(ChatMessage, message_id)
    if message:
        message.summary = summary
        db.commit()
        return True
    return False


def get_recent_qa_summaries(db: Session, session_id: int, limit: int = 5) -> List[str]:
    """최근 Q/A 쌍의 요약들을 가져옵니다."""
    stmt = select(ChatMessage).where(
        ChatMessage.session_id == session_id,
        ChatMessage.summary.isnot(None)
    ).order_by(desc(ChatMessage.created_at)).limit(limit)
    
    messages = db.execute(stmt).scalars().all()
    return [msg.summary for msg in messages if msg.summary]


def get_qa_pair_for_summary(db: Session, session_id: int, user_message_id: int) -> Optional[Dict]:
    """Q/A 쌍을 가져와서 요약 생성용 데이터로 반환합니다."""
    # 사용자 메시지 가져오기
    user_message = db.get(ChatMessage, user_message_id)
    if not user_message or user_message.message_type != "user":
        return None
    
    # 해당 사용자 메시지 이후의 첫 번째 bot 메시지 찾기
    stmt = select(ChatMessage).where(
        ChatMessage.session_id == session_id,
        ChatMessage.message_type == "bot",
        ChatMessage.created_at > user_message.created_at
    ).order_by(ChatMessage.created_at).limit(1)
    
    bot_message = db.execute(stmt).scalar_one_or_none()
    
    if bot_message:
        return {
            "user_message": user_message.text,
            "bot_message": bot_message.text,
            "user_message_id": user_message.id,
            "bot_message_id": bot_message.id
        }
    
    return None


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
