# 🔄 LangGraph 기반 LLM 아키텍처

## 📋 개요

기존 데이터 클래스 기반 구조를 **LangGraph 스타일의 Agent 기반 아키텍처**로 완전히 재설계했습니다. 각 Intent별로 전문화된 Agent가 독립적으로 동작하며, 공통 모듈을 통해 효율적인 검색과 요약을 수행합니다.

## 🏗️ 아키텍처 구조

### LangGraph 노드 플로우
```
Memory Analysis → Intent Analysis → Agent Execution → Summary Update
```

### 핵심 구성요소

#### 1. **LangGraph 노드들**
- **Memory Analysis Node**: 기억 필요 여부 판단 및 컨텍스트 로드
- **Intent Analysis Node**: 메모리 기반 또는 직접 의도 분석
- **Agent Execution Node**: 의도별 전문 Agent 실행
- **Summary Update Node**: Q/A 쌍별 요약 생성/업데이트

#### 2. **전문 Agent들**
- **SearchAgent**: 구체적 상품 검색 처리
- **ConversationAgent**: 상황별 대화형 추천
- **WeatherAgent**: 날씨 정보 + 의류 추천
- **GeneralAgent**: 일반 대화 처리
- **SummaryAgent**: 유사도 기반 요약 관리

#### 3. **공통 모듈들**
- **CommonSearchModule**: 모든 Agent가 사용하는 통합 검색
- **SummaryAgent**: Q/A 쌍별 지능적 요약 시스템

## 🔄 처리 플로우

### 1. Memory Analysis Node
```python
async def _memory_analysis_node(self, state: LangGraphState, db) -> LangGraphState:
    # 기억 필요 여부 판단
    state.needs_memory = self.memory_analyzer.analyze_memory_requirement(state.user_input)
    
    # 기억 필요시 Q/A 요약들 로드
    if state.needs_memory and db:
        state.context_summaries = get_recent_qa_summaries(db, state.session_id, limit=5)
    
    return state
```

### 2. Intent Analysis Node
```python
async def _intent_analysis_node(self, state: LangGraphState, db) -> LangGraphState:
    if state.needs_memory and state.context_summaries:
        # 메모리 기반 분석
        analysis_result = self.main_analyzer.analyze_with_prompt(
            state.user_input, context_str, ""
        )
    else:
        # 직접 분석
        intent_result = self.intent_analyzer.classify_intent(state.user_input, [])
    
    return state
```

### 3. Agent Execution Node
```python
async def _agent_execution_node(self, state: LangGraphState, available_products: List[Dict], db) -> LangGraphState:
    if state.intent == "search":
        result = self.search_agent.process_search_request(...)
    elif state.intent == "conversation":
        result = self.conversation_agent.process_conversation_request(...)
    elif state.intent == "weather":
        result = await self.weather_agent.process_weather_request(...)
    else:  # general
        result = self.general_agent.process_general_request(...)
    
    return state
```

### 4. Summary Update Node
```python
async def _summary_update_node(self, state: LangGraphState, db) -> LangGraphState:
    # Q/A 쌍 요약 생성/업데이트
    summary_result = self.summary_agent.process_qa_summary(
        state.user_input,
        state.final_message,
        existing_summary=None
    )
    
    return state
```

## 🎯 Agent 별 전문화

### SearchAgent
```python
class SearchAgent:
    def process_search_request(self, user_input: str, extracted_info: Dict, 
                             available_products: List[Dict], 
                             context_info: Optional[Dict] = None) -> SearchAgentResult:
        # 1. 검색 쿼리 구성
        # 2. 컨텍스트 기반 필터 구성
        # 3. CommonSearchModule로 상품 검색
        # 4. 결과 메시지 생성
```

### ConversationAgent
```python
class ConversationAgent:
    def process_conversation_request(self, user_input: str, extracted_info: Dict,
                                   available_products: List[Dict],
                                   context_summaries: Optional[List[str]] = None) -> ConversationAgentResult:
        # 1. LLM으로 상황별 추천 스펙 생성
        # 2. 추천 스펙을 검색 쿼리로 변환
        # 3. CommonSearchModule로 상품 검색
        # 4. 상의/하의 균형 맞추기
        # 5. 최종 메시지 생성
```

### WeatherAgent
```python
class WeatherAgent:
    async def process_weather_request(self, user_input: str, extracted_info: Dict,
                                    latitude: Optional[float] = None,
                                    longitude: Optional[float] = None) -> WeatherAgentResult:
        # 1. 지역 정보 처리
        # 2. 날씨 정보 조회
        # 3. 날씨 메시지 생성
        # 4. 의류 추천 연동 준비
```

## 📊 데이터 구조 변경

### LangGraphState
```python
@dataclass
class LangGraphState:
    user_input: str
    session_id: int
    user_id: int
    needs_memory: bool = False
    intent: str = ""
    extracted_info: Dict = None
    context_summaries: List[str] = None
    agent_result: Any = None
    final_message: str = ""
    products: List[Dict] = None
```

### ChatMessage 테이블 확장
```sql
-- 새로 추가된 컬럼
summary TEXT NULL  -- Q/A 쌍별 요약 저장
```

## 🔍 요약 시스템 (핵심 개선사항)

### 유사도 기반 요약 업데이트
```python
class SummaryAgent:
    def process_qa_summary(self, user_message: str, bot_message: str, 
                          existing_summary: Optional[str] = None) -> SummaryAgentResult:
        # 1. 새로운 요약 생성
        new_summary = self._generate_qa_summary(user_message, bot_message)
        
        if existing_summary:
            # 2. 유사도 계산
            similarity_score = self._calculate_similarity(existing_summary, new_summary)
            
            # 3. 유사도에 따른 처리
            if similarity_score >= 0.7:  # 70% 이상 유사
                return self._update_existing_summary(existing_summary, new_summary)  # 수정
            elif similarity_score <= 0.3:  # 30% 미만
                return new_summary  # 완전 교체
            else:
                return existing_summary  # 유지
```

### 처리 결과 유형
- **created**: 새로운 요약 생성
- **updated**: 기존 요약 수정
- **replaced**: 완전히 다른 내용으로 교체
- **skipped**: 기존 요약 유지

## 🛠️ 공통 모듈

### CommonSearchModule
```python
class CommonSearchModule:
    def search_products(self, query: SearchQuery, available_products: List[Dict], 
                       context_filters: Optional[Dict] = None) -> SearchResult:
        # 1. 기본 필터링 (색상, 카테고리, 브랜드, 가격)
        # 2. 컨텍스트 기반 추가 필터링
        # 3. 결과 정리 및 선택 (상의/하의 균형)
        # 4. 검색 요약 생성
```

### 컨텍스트 필터링
- **exclude_brands**: 이전 추천과 다른 브랜드 우선
- **price_differentiation**: 이전과 다른 가격대 우선
- **style_diversification**: 다양한 스타일 선택

## 🚀 API 엔드포인트

### 새로운 LangGraph API
```
POST /chat-new/new
- LangGraph 기반 처리
- Q/A 쌍별 요약 자동 생성
- Agent별 전문화된 응답

GET /chat-new/debug/memory-test
- 기억 필요 여부 테스트

GET /chat-new/analysis/{session_id}  
- 세션 분석 (요약 포함)
```

## 📈 성능 및 품질 개선

### 1. **모듈화된 구조**
- Agent별 독립적 개발/테스트 가능
- 공통 모듈 재사용으로 일관성 확보

### 2. **지능적 요약 시스템**
- 유사도 기반 요약 업데이트
- 불필요한 중복 방지
- 점진적 정보 축적

### 3. **컨텍스트 활용 극대화**
- Q/A 쌍별 세밀한 요약
- 메모리 기반 개인화 응답
- 이전 추천과의 차별화

### 4. **확장성**
- 새로운 Agent 쉽게 추가 가능
- Intent 추가 시 기존 코드 영향 최소
- 공통 모듈 활용으로 개발 효율성 증대

## 🔧 사용 예시

### 기억 기반 대화
```
사용자: "파란색 셔츠 추천해줘"
→ SearchAgent 실행 → 파란색 셔츠 추천 → 요약 저장

사용자: "이거 말고 좀 더 캐주얼한 걸로"  
→ 기억 필요 감지 → 이전 요약 로드 → ConversationAgent 실행 → 캐주얼 필터링
```

### Agent별 처리
```
"빨간 티셔츠" → SearchAgent → 정확 검색
"데이트룩 추천" → ConversationAgent → 상황별 추천  
"오늘 날씨" → WeatherAgent → 날씨 + 의류 추천
"고마워" → GeneralAgent → 일반 대화
```

## 🔄 마이그레이션 가이드

### 기존 시스템과의 호환성
- 기존 `/chat/` API는 그대로 유지
- 새로운 `/chat-new/` API로 점진적 전환
- 데이터베이스 스키마 확장 (summary 컬럼 추가)

### 개발자를 위한 확장 방법
1. **새로운 Agent 추가**: `services/agents/` 디렉토리에 추가
2. **새로운 Intent 지원**: Intent 분석기 및 해당 Agent 연결
3. **공통 기능 확장**: CommonSearchModule 기능 추가

이제 더욱 체계적이고 확장 가능한 LLM 서비스를 제공할 수 있습니다! 🎉
