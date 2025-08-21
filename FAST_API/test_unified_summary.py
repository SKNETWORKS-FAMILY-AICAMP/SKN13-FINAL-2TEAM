#!/usr/bin/env python3
"""
통합 서머리 에이전트 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from dotenv import load_dotenv
load_dotenv()

from services.agents.unified_summary_agent import UnifiedSummaryAgent

async def test_unified_summary():
    """통합 서머리 에이전트 테스트"""
    
    print("=== 통합 서머리 에이전트 테스트 시작 ===\n")
    
    agent = UnifiedSummaryAgent()
    
    # 테스트 케이스 1: 새로운 Q/A 요약 생성
    print("📝 테스트 1: 새로운 Q/A 요약 생성")
    user_input1 = "파란색 캐주얼 셔츠 추천해줘"
    llm_response1 = """안녕하세요! 파란색 캐주얼 셔츠를 추천해드릴게요! 🔍

**1. 유니클로 에어리즘 코튼 셔츠**
   📍 브랜드: 유니클로
   💰 가격: 29,900원
   🎨 특징: 통기성 좋은 면 소재, 시원한 착용감

**2. 무지 옥스포드 셔츠**  
   📍 브랜드: 무지
   💰 가격: 39,900원
   🎨 특징: 클래식한 옥스포드 원단, 데일리 착용 좋음

**3. 스파오 베이직 셔츠**
   📍 브랜드: 스파오
   💰 가격: 19,900원
   🎨 특징: 합리적인 가격, 다양한 코디 가능

모두 파란색 계열이며 캐주얼하게 입기 좋은 셔츠들입니다! 😊"""
    
    result1 = agent.process_complete_qa_summary(user_input1, llm_response1)
    
    print(f"성공: {result1.success}")
    print(f"액션: {result1.action_taken}")
    print(f"요약: {result1.summary_text}")
    print(f"신뢰도: {result1.confidence}")
    print(f"메타데이터: {result1.metadata}")
    print()
    
    # 테스트 케이스 2: 기존 요약 업데이트
    print("📝 테스트 2: 기존 요약 업데이트 (후속 질문)")
    user_input2 = "이거 말고 좀 더 저렴한 걸로 추천해줘"
    llm_response2 = """더 저렴한 파란색 셔츠를 추천해드릴게요! 💰

**1. 지오다노 베이직 셔츠**
   📍 브랜드: 지오다노
   💰 가격: 14,900원
   🎨 특징: 가성비 좋은 기본 셔츠

**2. 탑텐 캐주얼 셔츠**
   📍 브랜드: 탑텐
   💰 가격: 16,900원
   🎨 특징: 편안한 핏, 세탁 용이

이전 추천보다 1만원 이상 저렴한 옵션들입니다! 😊"""
    
    existing_summary = result1.summary_text
    result2 = agent.process_complete_qa_summary(user_input2, llm_response2, existing_summary)
    
    print(f"성공: {result2.success}")
    print(f"액션: {result2.action_taken}")
    print(f"요약: {result2.summary_text}")
    print(f"신뢰도: {result2.confidence}")
    print(f"이전 요약과 비교: {existing_summary}")
    print()
    
    # 테스트 케이스 3: 완전히 다른 주제
    print("📝 테스트 3: 완전히 다른 주제 (교체 테스트)")
    user_input3 = "오늘 서울 날씨 어때?"
    llm_response3 = """서울의 현재 날씨 정보입니다! 🌤️

**현재 기온**: 23°C
**날씨 상황**: 맑음
**습도**: 60%
**바람**: 남서풍 2m/s

오늘은 외출하기 좋은 날씨네요! 가벼운 옷차림을 추천드려요. ☀️"""
    
    result3 = agent.process_complete_qa_summary(user_input3, llm_response3, result2.summary_text)
    
    print(f"성공: {result3.success}")
    print(f"액션: {result3.action_taken}")
    print(f"요약: {result3.summary_text}")
    print(f"신뢰도: {result3.confidence}")
    print()
    
    # 테스트 케이스 4: 세션 개요 생성
    print("📝 테스트 4: 세션 개요 생성")
    qa_summaries = [result1.summary_text, result2.summary_text, result3.summary_text]
    session_overview = agent.generate_session_overview(qa_summaries)
    
    print(f"세션 개요: {session_overview}")
    print()
    
    # 테스트 케이스 5: 인사이트 추출
    print("📝 테스트 5: 요약 인사이트 추출")
    insights = agent.extract_summary_insights(result2.summary_text)
    
    print(f"추출된 인사이트: {insights}")
    print()
    
    print("=== 통합 서머리 에이전트 테스트 완료 ===")

if __name__ == "__main__":
    asyncio.run(test_unified_summary())
