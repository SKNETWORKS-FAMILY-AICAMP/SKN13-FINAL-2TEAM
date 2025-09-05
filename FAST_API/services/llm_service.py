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
# clothing_recommender는 삭제되었으므로 WeatherAgent의 메서드 사용
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
        """프롬프트 기반으로 intent 분류만 수행"""
        
        system_prompt = """당신은 의류 추천 시스템의 intent 분류기입니다.
사용자의 입력을 분석하여 intent만 분류해주세요.
**날씨와 상황이 합쳐진 의도도 weather로 분류하세요.**

컨텍스트 정보:
- 이전 대화 내용: {context}
- 세션 요약: {session_summary}

다음 JSON 형식으로 응답:
{{
    "intent": "search|conversation|followup|weather|general",
    "analysis_summary": "intent 분류 근거"
}}

Intent 분류 기준:
- search: 구체적인 상품 검색 ("파란색 셔츠", "청바지 추천", "나이키 운동화")
- conversation: 상황별 추천 ("데이트룩", "면접복", "파티룩")  
- followup: 이전 추천에 대한 후속 질문 ("이것들중에 제일 싼거", "더 비싼 것도 있어?", "첫 번째가 좋을까?")
- weather: 날씨 관련 ("오늘 날씨", "서울 날씨")
- general: 일반 대화 ("안녕", "고마워")

**중요**: 
1. 컨텍스트에서 이전에 상품 추천과 연관이 있는 질문이라면, 그 상품들에 대한 질문은 반드시 'followup'으로 분류하세요.
2. 필터링 조건 추출은 하지 마세요. intent 분류만 수행하세요.
3. 날씨와 상황이 합쳐진 의도도 weather로 분류하세요.
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
        """의도 분석 노드 - intent 분류만 수행"""
        context_str = " | ".join(state.context_summaries) if state.context_summaries else "이전 대화 없음"
        
        analysis_result = self.main_analyzer.analyze_with_prompt(
            state.user_input, context_str, ""
        )
        
        state.intent = analysis_result.get("intent", "general")
        # extracted_info는 빈 딕셔너리로 초기화 (필터링 조건은 각 Agent에서 처리)
        state.extracted_info = {}
        
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
                # Weather Agent 실행 (사용자 성별 정보 필요)
                # TODO: 실제 사용자 정보에서 성별 가져오기
                user_gender = "남성"  # 임시로 "남성" 사용
                
                result = await self.weather_agent.process_weather_request(
                    state.user_input,
                    state.extracted_info,
                    latitude=state.latitude,
                    longitude=state.longitude,
                    user_gender=user_gender
                )
                state.agent_result = result
                state.final_message = result.message
                state.products = result.products
                
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
    
    # 날씨 관련 기능들은 WeatherAgent로 이동됨
        