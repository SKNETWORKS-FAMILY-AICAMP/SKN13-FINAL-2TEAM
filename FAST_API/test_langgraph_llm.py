#!/usr/bin/env python3
"""
LangGraph 기반 LLM 서비스 테스트 스크립트
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_agents():
    """각 Agent 개별 테스트"""
    print("🧪 === Agent 개별 테스트 ===")
    
    # SearchAgent 테스트
    print("\n📍 SearchAgent 테스트")
    from services.agents.search_agent import SearchAgent
    
    search_agent = SearchAgent()
    
    test_products = [
        {"상품명": "파란색 캐주얼 셔츠", "색상": "파란색", "대분류": "상의", "한글브랜드명": "테스트브랜드", "원가": 50000},
        {"상품명": "검은색 청바지", "색상": "검은색", "대분류": "하의", "한글브랜드명": "데님브랜드", "원가": 80000}
    ]
    
    extracted_info = {
        "colors": ["파란색"],
        "categories": ["셔츠"],
        "keywords": ["파란색", "셔츠"]
    }
    
    search_result = search_agent.process_search_request(
        "파란색 셔츠 추천해줘",
        extracted_info,
        test_products
    )
    
    print(f"검색 결과: {search_result.success}")
    print(f"메시지: {search_result.message[:100]}...")
    print(f"상품 수: {len(search_result.products)}")
    
    # ConversationAgent 테스트
    print("\n💬 ConversationAgent 테스트")
    from services.agents.conversation_agent import ConversationAgent
    
    conversation_agent = ConversationAgent()
    
    extracted_info = {
        "situations": ["데이트"],
        "styles": ["로맨틱"],
        "keywords": ["데이트룩"]
    }
    
    conversation_result = conversation_agent.process_conversation_request(
        "데이트룩 추천해줘",
        extracted_info,
        test_products
    )
    
    print(f"대화 결과: {conversation_result.success}")
    print(f"메시지: {conversation_result.message[:100]}...")
    print(f"상품 수: {len(conversation_result.products)}")
    
    # WeatherAgent 테스트
    print("\n🌤️ WeatherAgent 테스트")
    from services.agents.weather_agent import WeatherAgent
    
    weather_agent = WeatherAgent()
    
    extracted_info = {
        "locations": ["서울"],
        "keywords": ["날씨"]
    }
    
    try:
        weather_result = await weather_agent.process_weather_request(
            "서울 날씨 알려줘",
            extracted_info
        )
        
        print(f"날씨 결과: {weather_result.success}")
        print(f"메시지: {weather_result.message[:100]}...")
        
    except Exception as e:
        print(f"날씨 테스트 오류 (예상됨 - API 키 필요): {e}")
    
    # GeneralAgent 테스트
    print("\n🗣️ GeneralAgent 테스트")
    from services.agents.general_agent import GeneralAgent
    
    general_agent = GeneralAgent()
    
    general_result = general_agent.process_general_request(
        "안녕하세요",
        {},
        context_summaries=["이전에 파란색 셔츠 추천 받음"]
    )
    
    print(f"일반 대화 결과: {general_result.success}")
    print(f"메시지: {general_result.message[:100]}...")

async def test_summary_agent():
    """UnifiedSummaryAgent 테스트"""
    print("\n📝 === UnifiedSummaryAgent 테스트 ===")
    
    from services.agents.unified_summary_agent import UnifiedSummaryAgent
    
    summary_agent = UnifiedSummaryAgent()
    
    # 새로운 Q/A 요약 생성
    print("\n1. 새로운 요약 생성")
    result1 = summary_agent.process_complete_qa_summary(
        "파란색 셔츠 추천해줘",
        "파란색 캐주얼 셔츠 3개를 추천해드렸습니다. 브랜드별 특징과 가격대를 확인해보세요."
    )
    
    print(f"액션: {result1.action_taken}")
    print(f"요약: {result1.summary_text}")
    print(f"신뢰도: {result1.confidence}")
    
    # 유사한 내용으로 업데이트
    print("\n2. 유사한 내용으로 업데이트")
    result2 = summary_agent.process_complete_qa_summary(
        "파란색 셔츠 다른 브랜드로 추천해줘",
        "파란색 셔츠를 다른 브랜드 3개로 추천해드렸습니다.",
        existing_summary=result1.summary_text
    )
    
    print(f"액션: {result2.action_taken}")
    print(f"요약: {result2.summary_text}")
    print(f"신뢰도: {result2.confidence}")
    
    # 완전히 다른 내용
    print("\n3. 완전히 다른 내용으로 교체")
    result3 = summary_agent.process_complete_qa_summary(
        "오늘 날씨 어때?",
        "서울의 현재 기온은 23도이고 맑은 날씨입니다.",
        existing_summary=result1.summary_text
    )
    
    print(f"액션: {result3.action_taken}")
    print(f"요약: {result3.summary_text}")
    print(f"신뢰도: {result3.confidence}")

async def test_common_search():
    """CommonSearchModule 테스트"""
    print("\n🔍 === CommonSearchModule 테스트 ===")
    
    from services.common_search import CommonSearchModule, SearchQuery
    
    search_module = CommonSearchModule()
    
    test_products = [
        {"상품명": "파란색 캐주얼 셔츠", "색상": "파란색", "대분류": "상의", "한글브랜드명": "브랜드A", "원가": 50000},
        {"상품명": "빨간색 니트", "색상": "빨간색", "대분류": "상의", "한글브랜드명": "브랜드B", "원가": 70000},
        {"상품명": "검은색 청바지", "색상": "검은색", "대분류": "하의", "한글브랜드명": "브랜드C", "원가": 80000},
        {"상품명": "회색 슬랙스", "색상": "회색", "대분류": "하의", "한글브랜드명": "브랜드D", "원가": 90000},
    ]
    
    # 기본 검색
    print("\n1. 기본 색상 검색")
    query1 = SearchQuery(colors=["파란색"])
    result1 = search_module.search_products(query1, test_products)
    
    print(f"검색 요약: {result1.search_summary}")
    print(f"상품 수: {len(result1.products)}")
    
    # 컨텍스트 필터링
    print("\n2. 컨텍스트 기반 필터링")
    query2 = SearchQuery(colors=["빨간색", "파란색"])
    context_filters = {
        "exclude_brands": ["브랜드A"],  # 이전에 추천된 브랜드 제외
        "style_diversification": True
    }
    result2 = search_module.search_products(query2, test_products, context_filters)
    
    print(f"검색 요약: {result2.search_summary}")
    print(f"상품 수: {len(result2.products)}")
    print(f"적용된 필터: {result2.applied_filters}")

async def test_langgraph_flow():
    """LangGraph 전체 플로우 테스트"""
    print("\n🔄 === LangGraph 전체 플로우 테스트 ===")
    
    from services.new_llm_service import NewLLMService, LangGraphState
    
    llm_service = NewLLMService()
    
    test_products = [
        {"상품명": "파란색 캐주얼 셔츠", "색상": "파란색", "대분류": "상의", "한글브랜드명": "브랜드A", "원가": 50000, "상품코드": "A001"},
        {"상품명": "검은색 청바지", "색상": "검은색", "대분류": "하의", "한글브랜드명": "브랜드B", "원가": 80000, "상품코드": "B001"}
    ]
    
    test_cases = [
        {
            "input": "파란색 셔츠 추천해줘",
            "description": "직접 검색 (기억 불필요)"
        },
        {
            "input": "이거 말고 다른 브랜드로 추천해줘", 
            "description": "컨텍스트 기반 검색 (기억 필요)"
        },
        {
            "input": "데이트룩 추천해줘",
            "description": "상황별 추천"
        },
        {
            "input": "고마워",
            "description": "일반 대화"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"입력: '{test_case['input']}'")
        
        try:
            response = await llm_service.process_user_input(
                user_input=test_case['input'],
                session_id=1,
                user_id=1,
                available_products=test_products,
                db=None  # DB 없이 테스트
            )
            
            print(f"✅ 성공")
            print(f"메시지: {response.final_message[:100]}...")
            print(f"상품 수: {len(response.products)}")
            print(f"메타데이터: {response.metadata}")
            
        except Exception as e:
            print(f"❌ 오류: {e}")

async def main():
    """메인 테스트 함수"""
    print("🚀 LangGraph LLM 서비스 테스트 시작")
    
    try:
        await test_agents()
        await test_summary_agent()
        await test_common_search()
        await test_langgraph_flow()
        
        print("\n✅ 모든 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
