#!/usr/bin/env python3
"""
특정 세션의 Q/A 데이터 확인 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db import SessionLocal
from crud.chat_crud import get_session_messages

def test_session_qa(session_id: str, user_id: int):
    """특정 세션의 Q/A 데이터 확인"""
    
    print(f"=== 세션 {session_id} Q/A 데이터 확인 ===")
    print(f"사용자 ID: {user_id}")
    print()
    
    db = SessionLocal()
    try:
        # 세션 메시지 가져오기
        messages = get_session_messages(db, session_id, user_id)
        
        print(f"총 메시지 수: {len(messages)}")
        print()
        
        if not messages:
            print("❌ 메시지가 없습니다.")
            return
        
        # 메시지 출력
        for i, msg in enumerate(messages, 1):
            msg_type = msg.get('type', 'unknown')
            msg_text = msg.get('text', '')
            created_at = msg.get('created_at', '')
            
            print(f"[{i}] {msg_type.upper()}: {msg_text[:100]}...")
            print(f"    시간: {created_at}")
            print()
        
        # Q/A 쌍 구성 테스트
        print("=== Q/A 쌍 구성 테스트 ===")
        qa_pairs = []
        user_msg = None
        
        # 시간순 정렬
        messages.sort(key=lambda x: x.get('created_at', ''), reverse=False)
        
        for msg in messages:
            msg_type = msg.get('type')
            msg_text = msg.get('text', '')
            
            if msg_type == "user":
                user_msg = msg_text
            elif msg_type == "bot" and user_msg:
                qa_pairs.append({
                    "question": user_msg,
                    "answer": msg_text,
                })
                print(f"Q: {user_msg}")
                print(f"A: {msg_text[:200]}...")
                print("-" * 50)
                user_msg = None
        
        print(f"총 Q/A 쌍: {len(qa_pairs)}개")
        
        # 팔로우업 에이전트 테스트
        print("\n=== 팔로우업 에이전트 테스트 ===")
        from services.agents.followup_agent import FollowUpAgent
        
        agent = FollowUpAgent()
        
        # 후속 질문 테스트
        follow_up_questions = [
            "저거 중에 제일 싼거",
            "가장 비싼 건 뭐야?",
            "첫 번째 거 어때?"
        ]
        
        for question in follow_up_questions:
            print(f"\n후속 질문: {question}")
            result = agent.process_follow_up_question(question, db, user_id, session_id)
            print(f"성공: {result.success}")
            print(f"응답: {result.message}")
            print("-" * 30)
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    # 실제 테스트 데이터
    session_id = "test-uuid-session-id"  # UUID 형식으로 변경
    user_id = 2
    
    test_session_qa(session_id, user_id)
