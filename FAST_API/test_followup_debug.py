#!/usr/bin/env python3
"""
팔로우업 에이전트 디버깅 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def test_followup_with_mock_data():
    """모의 데이터로 팔로우업 에이전트 테스트"""
    
    print("=== 팔로우업 에이전트 디버깅 테스트 ===\n")
    
    from services.agents.followup_agent import FollowUpAgent
    
    agent = FollowUpAgent()
    
    # 모의 Q/A 데이터
    mock_qa_data = [
        {
            "question": "파란색 셔츠 추천해줘",
            "answer": """'파란색 셔츠' 검색 결과입니다! 🔍

👕 **상의**
**1. STARS OXFORD LSL DARK GREY**
   📍 브랜드: 스투시
   💰 가격: 139,000원

**2. 준 플라이 셔츠**
   📍 브랜드: 아노블리어
   💰 가격: 99,000원

**3. Button Down Shirts WhiteBlue**
   📍 브랜드: 라클리크
   💰 가격: 75,000원"""
        }
    ]
    
    # 후속 질문 테스트
    follow_up_question = "저거 중에 제일 싼거 뭐야?"
    
    print(f"후속 질문: {follow_up_question}")
    print()
    
    # LLM 답변 생성 테스트
    answer = agent._generate_followup_answer_with_llm(follow_up_question, mock_qa_data)
    
    print("LLM 답변:")
    print(answer)
    print()
    
    # 키워드 감지 테스트
    is_followup = agent.is_follow_up_question(follow_up_question)
    print(f"후속 질문 감지: {is_followup}")
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_followup_with_mock_data())
