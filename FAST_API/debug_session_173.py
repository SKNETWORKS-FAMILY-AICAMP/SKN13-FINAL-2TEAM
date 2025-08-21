#!/usr/bin/env python3
"""
세션 173 디버깅 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

def debug_session_173():
    """세션 173의 실제 데이터 확인"""
    
    print("=== 세션 173 디버깅 ===\n")
    
    from db import SessionLocal
    from crud.chat_crud import get_session_messages, get_chat_session_by_id
    
    session_id = 173
    user_id = 2
    
    db = SessionLocal()
    try:
        print(f"🔍 세션 정보 확인")
        session = get_chat_session_by_id(db, session_id, user_id)
        
        if session:
            print(f"✅ 세션 {session_id} 존재함")
            print(f"  - 세션명: {session.session_name}")
            print(f"  - 생성일: {session.created_at}")
            print(f"  - 수정일: {session.updated_at}")
        else:
            print(f"❌ 세션 {session_id}를 찾을 수 없음")
            return
        
        print(f"\n🔍 메시지 로드 테스트")
        messages = get_session_messages(db, session_id, user_id)
        
        print(f"✅ 총 {len(messages)}개 메시지 로드됨")
        
        if not messages:
            print("❌ 메시지가 없습니다")
            return
        
        print(f"\n📝 메시지 상세:")
        for i, msg in enumerate(messages):
            msg_type = msg.get('type', 'unknown')
            msg_text = msg.get('text', '')
            msg_id = msg.get('id', 'unknown')
            created_at = msg.get('created_at', 'unknown')
            
            print(f"[{i+1}] ID: {msg_id}")
            print(f"    타입: {msg_type}")
            print(f"    내용: {msg_text[:100]}...")
            print(f"    시간: {created_at}")
            print()
        
        # 팔로우업 에이전트 테스트
        print(f"🤖 팔로우업 에이전트 테스트")
        from services.agents.followup_agent import FollowUpAgent
        
        agent = FollowUpAgent()
        
        test_question = "저거중에 제일 싼거"
        print(f"테스트 질문: {test_question}")
        
        # Q/A 데이터 로드 테스트
        qa_data = agent._get_recent_qa_data(db, user_id, session_id)
        print(f"Q/A 데이터: {len(qa_data)}개")
        
        for i, qa in enumerate(qa_data):
            print(f"Q{i+1}: {qa['question']}")
            print(f"A{i+1}: {qa['answer'][:100]}...")
            print()
        
        # 실제 팔로우업 처리 테스트
        print(f"🚀 팔로우업 처리 테스트")
        result = agent.process_follow_up_question(test_question, db, user_id, session_id)
        
        print(f"결과: success={result.success}")
        print(f"메시지: {result.message}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug_session_173()
