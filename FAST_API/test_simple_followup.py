#!/usr/bin/env python3
"""
간소화된 팔로우업 에이전트 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# 모의 데이터로 테스트
def test_simplified_followup():
    """간소화된 팔로우업 에이전트 테스트"""
    
    print("=== 간소화된 팔로우업 에이전트 테스트 ===\n")
    
    from services.agents.followup_agent import FollowUpAgent
    
    agent = FollowUpAgent()
    
    # 모의 Q/A 데이터
    mock_qa_data = [
        {
            "question": "파란색 캐주얼 셔츠 추천해줘",
            "answer": """파란색 캐주얼 셔츠를 추천해드릴게요! 🔍

**1. 유니클로 에어리즘 코튼 셔츠**
   📍 브랜드: 유니클로
   💰 가격: 29,900원
   🎨 특징: 통기성 좋은 면 소재

**2. 무지 옥스포드 셔츠**  
   📍 브랜드: 무지
   💰 가격: 39,900원
   🎨 특징: 클래식한 옥스포드 원단

**3. 스파오 베이직 셔츠**
   📍 브랜드: 스파오
   💰 가격: 19,900원
   🎨 특징: 합리적인 가격"""
        }
    ]
    
    # 다양한 후속 질문 테스트
    test_questions = [
        "가장 싼 거는 뭐야?",
        "첫 번째 거 어때?",
        "브랜드별로 특징 비교해줘",
        "어떤 걸 고르면 좋을까?",
        "면접 볼 때 입기 좋은 건?"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"📝 테스트 {i}: {question}")
        
        # 직접 LLM 메서드 호출 (DB 없이 테스트)
        answer = agent._generate_followup_answer_with_llm(question, mock_qa_data)
        
        print(f"답변: {answer}")
        print("-" * 50)
        print()

if __name__ == "__main__":
    test_simplified_followup()
