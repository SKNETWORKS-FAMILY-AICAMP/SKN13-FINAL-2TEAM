import os
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv
import asyncio

# Agent imports
from services.agents.search_agent import SearchAgent, SearchAgentResult
from services.agents.conversation_agent import ConversationAgent, ConversationAgentResult
from services.agents.weather_agent import WeatherAgent, WeatherAgentResult
from services.agents.general_agent import GeneralAgent, GeneralAgentResult
from services.agents.unified_summary_agent import UnifiedSummaryAgent, UnifiedSummaryResult
from services.agents.followup_agent import FollowUpAgent, FollowUpAgentResult

# Legacy imports for compatibility
# Legacy IntentAnalyzer 제거됨 - 현재 MainAnalyzer만 사용
from services.clothing_recommender import recommend_clothing_by_weather
# Legacy imports 완전 제거됨 - 모든 기능이 에이전트로 통합됨
from crud.chat_crud import (get_recent_qa_summaries, get_qa_pair_for_summary, 
                           update_message_summary, get_chat_history_for_llm)
from utils.safe_utils import safe_lower

load_dotenv()

# IntentResult 클래스 정의 (기존 intent_analyzer에서 이동)
@dataclass
class IntentResult:
    intent: str  # 'search', 'conversation', 'followup', 'weather', 'general'
    confidence: float
    extracted_info: Dict
    original_query: str

@dataclass
class LangGraphState:
    """LangGraph 상태 관리"""
    user_input: str
    session_id: str  # UUID를 문자열로 처리
    user_id: int
    intent: str = ""
    extracted_info: Dict = None
    context_summaries: List[str] = None
    agent_result: Any = None
    final_message: str = ""
    products: List[Dict] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    def __post_init__(self):
        if self.extracted_info is None:
            self.extracted_info = {}
        if self.context_summaries is None:
            self.context_summaries = []
        if self.products is None:
            self.products = []

@dataclass
class LLMResponse:
    """LLM 응답 구조"""
    final_message: str
    products: List[Dict]
    analysis_result: Any  # IntentResult 또는 MainAnalysisResult
    summary_result: Optional[UnifiedSummaryResult] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}



class MainAnalyzer:
    """새로운 프롬프트 기반 메인 분석기 (컨텍스트 포함 의도 분석용)"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    
    def analyze_with_prompt(self, user_input: str, context: str = "", session_summary: str = "") -> Dict:
        """프롬프트 기반으로 종합적인 분석 수행"""
        
        system_prompt = """당신은 의류 추천 시스템의 메인 분석기입니다.
사용자의 입력을 종합적으로 분석하여 다음을 수행해주세요:

1. Intent 분류: search, conversation, weather, general
2. 필터링 조건 추출
3. 분석 요약 생성

컨텍스트 정보:
- 이전 대화 내용: {context}
- 세션 요약: {session_summary}

다음 JSON 형식으로 응답:
{{
    "intent": "search|conversation|followup|weather|general",
    "confidence": 0.0-1.0,
    "filtering_conditions": {{
        "colors": ["추출된 색상들"],
        "categories": ["추출된 카테고리들"],
        "situations": ["추출된 상황들"],
        "styles": ["추출된 스타일들"],
        "brands": ["추출된 브랜드들"],
        "locations": ["지역명들"]
    }},
    "analysis_summary": "분석 결과 요약"
}}

Intent 분류 기준:
- search: 구체적인 상품 검색 ("파란색 셔츠", "청바지 추천", "나이키 운동화")
- conversation: 상황별 추천 ("데이트룩", "면접복", "파티룩")  
- followup: 이전 추천에 대한 후속 질문 ("이것들중에 제일 싼거", "더 비싼 것도 있어?", "첫 번째가 좋을까?")
- weather: 날씨 관련 ("오늘 날씨", "서울 날씨")
- general: 일반 대화 ("안녕", "고마워")

필터링 조건 추출 기준:
- colors: 색상 관련 ("빨간색", "파란색", "검은색", "흰색", "베이지", "네이비", "카키", "민트", "와인", "올리브" 등)
- categories: 대분류/소분류 ("상의", "바지", "스커트", "원피스", "긴소매", "반소매", "후드티", "니트/스웨터", "셔츠/블라우스", "피케/카라", "슬리브리스", "데님팬츠", "코튼팬츠", "슈트팬츠/슬랙스", "카고팬츠", "트레이닝/조거팬츠", "숏팬츠", "롱스커트", "미니스커트", "미디스커트", "맥시원피스", "미니원피스", "미디원피스")
- brands: 브랜드명 ("나이키", "아디다스", "유니클로", "ZARA", "H&M" 등)
- situations: 상황/장소 ("데이트", "면접", "파티", "운동", "여행", "출근", "캐주얼" 등)
- styles: 스타일 ("캐주얼", "정장", "스포티", "빈티지", "미니멀" 등)

**중요**: 
1. 컨텍스트에서 이전에 상품 추천과 연관이 있는 질문이라면, 그 상품들에 대한 질문은 반드시 'followup'으로 분류하세요.
"""
        messages = [
            {"role": "system", "content": system_prompt.format(
                context=context,
                session_summary=session_summary
            )},
            {"role": "user", "content": f"사용자 입력: {user_input}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=800
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"메인 분석 오류: {e}")
            # 오류 시 기본값 반환
            return {
                "intent": "general",
                "confidence": 0.0,
                "filtering_conditions": {},
                "analysis_summary": "분석 중 오류 발생"
            }



class LLMService:
    """LangGraph 기반 LLM 서비스"""
    
    def __init__(self):
        # Core analyzers (메모리 분석기 제거, 메인 분석기만 사용)
        self.main_analyzer = MainAnalyzer()
        
        # Specialized agents
        self.search_agent = SearchAgent()
        self.conversation_agent = ConversationAgent()
        self.weather_agent = WeatherAgent()
        self.general_agent = GeneralAgent()
        self.unified_summary_agent = UnifiedSummaryAgent()
        self.followup_agent = FollowUpAgent()
        print("✅ FollowUpAgent 초기화 완료")
        
        # 기존 IntentAnalyzer 제거 - 항상 MainAnalyzer 사용
    
    async def process_user_input(self, user_input: str, session_id: str, user_id: int, 
                                available_products: List[Dict], db=None, 
                                latitude: Optional[float] = None, 
                                longitude: Optional[float] = None) -> LLMResponse:
        """LangGraph 스타일로 사용자 입력 처리"""
        

        
        # 초기 상태 생성
        state = LangGraphState(
            user_input=user_input,
            session_id=session_id,
            user_id=user_id,
            latitude=latitude,
            longitude=longitude
        )
        
        # LangGraph 스타일 처리 플로우
        state = await self._memory_analysis_node(state, db)
        state = await self._intent_analysis_node(state, db)
        state = await self._agent_execution_node(state, available_products, db)
        state = await self._summary_update_node(state, db)
        
        # 분석 결과 구성 (항상 IntentResult로 통일)
        
        # 항상 IntentResult로 통일
        analysis_result = IntentResult(
            intent=state.intent,
            confidence=1.0,
            extracted_info=state.extracted_info if hasattr(state, 'extracted_info') else {},
            original_query=state.user_input
        )

        # 최종 응답 구성
        return LLMResponse(
            final_message=state.final_message,
            products=state.products,
            analysis_result=analysis_result,
            summary_result=state.summary_result if hasattr(state, 'summary_result') else None,
            metadata={
                "intent": state.intent,
                "always_uses_context": True,
                "agent_type": getattr(analysis_result, 'metadata', {}).get('agent_type', state.intent),
                "context_summaries_count": len(state.context_summaries)
            }
        )
    
    async def _memory_analysis_node(self, state: LangGraphState, db) -> LangGraphState:
        """메모리 로드 노드 - 항상 컨텍스트 로드"""
        if db:
            state.context_summaries = get_recent_qa_summaries(db, state.session_id, limit=3)
        else:
            state.context_summaries = []
        
        return state
    
    async def _intent_analysis_node(self, state: LangGraphState, db) -> LangGraphState:
        """의도 분석 노드 - 항상 메모리 기반 분석 사용"""
        context_str = " | ".join(state.context_summaries) if state.context_summaries else "이전 대화 없음"
        
        analysis_result = self.main_analyzer.analyze_with_prompt(
            state.user_input, context_str, ""
        )
        
        state.intent = analysis_result.get("intent", "general")
        state.extracted_info = analysis_result.get("filtering_conditions", {})
        
        return state
    
    async def _agent_execution_node(self, state: LangGraphState, available_products: List[Dict], db) -> LangGraphState:
        """Agent 실행 노드 - 의도에 따라 적절한 Agent 호출"""
        try:
            if state.intent == "followup":
                result = self.followup_agent.process_follow_up_question(
                    state.user_input, 
                    db, 
                    state.user_id,
                    state.session_id
                )
                
                state.agent_result = result
                state.final_message = result.message
                state.products = result.products
                
            elif state.intent == "search":
                # Search Agent 실행
                result = self.search_agent.process_search_request(
                    state.user_input, 
                    state.extracted_info, 
                    available_products,
                    context_info={"previous_summaries": state.context_summaries} if state.context_summaries else None,
                    db=db,
                    user_id=state.user_id
                )
                state.agent_result = result
                state.final_message = result.message
                state.products = result.products
                
            elif state.intent == "conversation":
                # Conversation Agent 실행 (순수 상황별 추천만)
                result = self.conversation_agent.process_conversation_request(
                    state.user_input,
                    state.extracted_info,
                    available_products,
                    context_summaries=state.context_summaries,
                    db=db,
                    user_id=state.user_id
                )
                state.agent_result = result
                state.final_message = result.message
                state.products = result.products
                
            elif state.intent == "weather":
                # Weather Agent 실행
                result = await self.weather_agent.process_weather_request(
                    state.user_input,
                    state.extracted_info,
                    latitude=state.latitude,
                    longitude=state.longitude
                )
                state.agent_result = result
                state.final_message = result.message
                state.products = result.products
                
                # 날씨 응답에 의류 추천 추가
                if result.success:
                    state = await self._enhance_weather_with_clothing(state, db)
                
            else:  # general
                # General Agent 실행
                result = self.general_agent.process_general_request(
                    state.user_input,
                    state.extracted_info,
                    context_summaries=state.context_summaries
                )
                state.agent_result = result
                state.final_message = result.message
                state.products = result.products
                
        except Exception as e:
            # 오류 발생 시 일반 에이전트로 fallback
            try:
                result = self.general_agent.process_general_request(
                    state.user_input,
                    state.extracted_info if hasattr(state, 'extracted_info') else {},
                    context_summaries=state.context_summaries
                )
                state.agent_result = result
                state.final_message = result.message
                state.products = result.products
            except Exception:
                state.final_message = "죄송합니다. 요청을 처리하는 중 오류가 발생했습니다."
                state.products = []
        
        return state
    
    async def _summary_update_node(self, state: LangGraphState, db) -> LangGraphState:
        """통합 요약 업데이트 노드 - LLM 최종 답변까지 포함한 완전한 요약"""
        if not db:
            return state
        
        try:
            # 기존 요약 조회
            existing_summary = None
            try:
                from crud.chat_crud import get_recent_qa_summaries
                recent_summaries = get_recent_qa_summaries(db, state.session_id, limit=1)
                if recent_summaries:
                    existing_summary = recent_summaries[0]
            except Exception:
                pass
            
            # 통합 서머리 에이전트로 완전한 Q/A 요약 생성
            summary_result = self.unified_summary_agent.process_complete_qa_summary(
                user_input=state.user_input,
                llm_final_response=state.final_message,
                existing_summary=existing_summary
            )
            
            # 상태에 요약 정보 저장
            state.summary_to_save = summary_result.summary_text
            state.summary_result = summary_result
            
        except Exception:
            # 오류 시 간단한 fallback 요약 생성
            fallback_summary = f"Q: {state.user_input[:30]}... → A: {state.final_message[:50]}..."
            state.summary_to_save = fallback_summary
        
        return state
    
    async def _enhance_weather_with_clothing(self, state: LangGraphState, db) -> LangGraphState:
        """날씨 응답에 실제 상품 추천 추가 (CommonSearch 사용)"""
        try:
            # 날씨 정보에서 기온 추출
            weather_info = self.weather_agent.extract_weather_info_from_message(state.final_message)
            
            if weather_info and weather_info.get("temperature") is not None:
                # 사용자 성별 정보 가져오기 (임시로 "남성" 사용)
                user_gender = "남성"  # TODO: 실제 사용자 정보에서 가져오기
                
                # 의류 카테고리 추천 생성
                recommended_clothing = recommend_clothing_by_weather(
                    weather_info["weather_description"], 
                    user_gender
                )
                
                # CommonSearch를 사용해 실제 상품 검색
                if recommended_clothing and any(recommended_clothing.values()):
                    weather_products = await self._search_weather_products(
                        recommended_clothing, state, db
                    )
                    
                    if weather_products:
                        # 기존 상품 목록에 추가
                        state.products.extend(weather_products[:3])  # 최대 3개 추가
                        
                        # 날씨 기반 추천도 recommendation 테이블에 저장
                        self._save_weather_recommendations(db, state.user_id, weather_info["weather_description"], weather_products[:3])
                        
                        # 추천 메시지에 실제 상품 정보 추가
                        clothing_message = f"\n\n🎯 **오늘 날씨 맞춤 상품**\n"
                        for i, product in enumerate(weather_products[:3], 1):
                            product_name = product.get('상품명', '상품명 없음')
                            brand = product.get('한글브랜드명', '브랜드 없음')
                            price = product.get('원가', 0)
                            
                            clothing_message += f"**{i}. {product_name}**\n"
                            clothing_message += f"   📍 브랜드: {brand}\n"
                            if price:
                                clothing_message += f"   💰 가격: {price:,}원\n"
                            clothing_message += "\n"
                        
                        state.final_message += clothing_message
                    else:
                        # 실제 상품이 없으면 기존 카테고리 추천만 표시
                        clothing_parts = []
                        for category, items in recommended_clothing.items():
                            if items:
                                clothing_parts.append(f"{category}: {', '.join(items)}")
                        
                        if clothing_parts:
                            clothing_message = f"\n\n🎯 **오늘 날씨 추천**\n{', '.join(clothing_parts)}을(를) 추천해 드려요!"
                            state.final_message += clothing_message
                        
        except Exception as e:
            print(f"날씨 의류 추천 오류: {e}")
        
        return state
    
    async def _search_weather_products(self, recommended_clothing: Dict, state: LangGraphState, db) -> List[Dict]:
        """날씨 기반 추천 의류의 실제 상품 검색"""
        try:
            from services.common_search import CommonSearchModule, SearchQuery
            from data_store import clothing_data
            
            search_module = CommonSearchModule()
            all_products = []
            
            # 각 카테고리별로 검색
            for category, items in recommended_clothing.items():
                if not items:
                    continue
                    
                # 검색 쿼리 구성
                search_query = SearchQuery(
                    categories=[category] + items,  # 카테고리와 아이템들을 모두 카테고리로 사용
                    colors=[],  # 색상 제한 없음
                    situations=["날씨"],
                    styles=[]
                )
                
                # 상품 검색
                if clothing_data:
                    search_result = search_module.search_products(
                        query=search_query,
                        available_products=clothing_data
                    )
                    
                    if search_result.products:
                        all_products.extend(search_result.products[:2])  # 카테고리당 최대 2개
            
            # 중복 제거
            seen_ids = set()
            unique_products = []
            for product in all_products:
                product_id = product.get("상품코드", "")
                if product_id and product_id not in seen_ids:
                    seen_ids.add(product_id)
                    unique_products.append(product)
            
            print(f"날씨 기반 상품 검색 결과: {len(unique_products)}개")
            return unique_products[:4]  # 최대 4개 반환
            
        except Exception as e:
            print(f"날씨 상품 검색 오류: {e}")
            return []
    
    def _save_weather_recommendations(self, db, user_id: int, weather_desc: str, products: List[Dict]):
        """날씨 기반 추천을 recommendation 테이블에 저장 - 챗봇 라우터에서만 저장하도록 비활성화"""
        # 챗봇 라우터에서만 추천을 저장하도록 비활성화
        # 중복 저장 방지를 위해 WeatherAgent에서는 저장하지 않음
        print("ℹ️ WeatherAgent: 추천 저장은 챗봇 라우터에서 처리됩니다.")
        return
        
        # 기존 코드 (주석 처리)
        """
        try:
            from crud.recommendation_crud import create_multiple_recommendations, get_user_recommendations
            
            # 최근 추천 기록 조회하여 중복 체크
            recent_recommendations = get_user_recommendations(db, user_id, limit=20)
            recent_item_ids = {rec.item_id for rec in recent_recommendations}
            
            recommendations_data = []
            for product in products:
                item_id = product.get("상품코드", 0)
                if item_id and item_id not in recent_item_ids:
                    recommendations_data.append({
                        "item_id": item_id,
                        "query": f"날씨 기반 추천 ({weather_desc})",
                        "reason": f"{weather_desc}에 적합한 의류"
                    })
                    recent_item_ids.add(item_id)  # 중복 방지를 위해 추가
            
            if recommendations_data:
                create_multiple_recommendations(db, user_id, recommendations_data)
                print(f"✅ 날씨 기반 추천 {len(recommendations_data)}개를 recommendation 테이블에 저장했습니다.")
            else:
                print("⚠️ 저장할 날씨 추천이 없습니다 (중복 제거 후).")
                
        except Exception as e:
            print(f"❌ 날씨 추천 저장 중 오류: {e}")
            # 저장 실패해도 추천은 계속 진행
        """
    
    # Legacy methods 완전 제거됨 - LangGraph 에이전트 시스템으로 대체
    # 모든 처리가 _agent_execution_node에서 통합 처리됨
