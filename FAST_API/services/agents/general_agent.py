"""
General Intent Agent
일반적인 대화를 처리하는 에이전트
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

from utils.safe_utils import safe_lower

load_dotenv()

@dataclass
class GeneralAgentResult:
    """General Agent 결과"""
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

class GeneralAgent:
    """일반 대화 에이전트"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
        
        # 미리 정의된 응답들 (확장됨)
        self.predefined_responses = {
            # 인사
            "안녕": "안녕하세요! 👋 의류 추천을 도와드릴게요. 어떤 옷을 찾고 계신가요?",
            "하이": "안녕하세요! 👋 패션 상담사 챗봇입니다. 무엇을 도와드릴까요?",
            "hello": "Hello! 👋 의류 추천 서비스입니다. 어떤 스타일을 찾고 계신가요?",
            
            # 도움말 및 기능 안내
            "도움말": "저는 의류 추천 챗봇입니다! 🛍️\n\n• 구체적인 검색: '파란색 셔츠 추천해줘'\n• 상황별 추천: '데이트룩 추천해줘'\n• 날씨 정보: '오늘 날씨 어때?'\n• 후속 질문: '이것들 중에 제일 싼 거'\n• 일반 대화도 가능해요!",
            "기능": "다음과 같은 기능을 제공해요! ✨\n\n🔍 **상품 검색**: 색상, 종류별 검색\n💬 **상황별 추천**: 데이트, 면접, 파티 등\n🌤️ **날씨 기반 추천**: 실시간 날씨에 맞는 옷\n🔄 **후속 질문**: 가격 비교, 브랜드 문의 등",
            "뭐할수있어": "여러 가지 도움을 드릴 수 있어요! 😊\n\n• 옷 추천 (색상, 스타일별)\n• 상황별 코디 제안\n• 날씨에 맞는 의류 추천\n• 가격대별 상품 찾기\n• 브랜드 정보 제공",
            
            # 감사 표현
            "감사": "천만에요! 😊 더 필요한 것이 있으시면 언제든 말씀해주세요.",
            "고마워": "별말씀을요! 😊 좋은 옷 찾으시길 바라요!",
            "고맙다": "도움이 되어서 기뻐요! 😊 다른 궁금한 것도 언제든 물어보세요.",
            "땡큐": "You're welcome! 😊 더 도움이 필요하시면 말씀해주세요!",
            
            # 칭찬 및 긍정 반응
            "잘했어": "감사합니다! 😊 더 좋은 추천을 위해 계속 노력하겠습니다!",
            "좋아": "기뻐해주셔서 감사해요! 😊 다른 도움이 필요하시면 언제든 말씀해주세요.",
            "최고": "와! 감사합니다! 🥰 더 멋진 추천으로 보답하겠어요!",
            "완벽": "정말 기뻐요! ✨ 완벽한 스타일링 도움을 드리겠습니다!",
            
            # 작별 인사
            "안녕히": "안녕히 가세요! 👋 좋은 하루 되시고, 또 찾아주세요!",
            "잘가": "네, 안녕히 가세요! 😊 멋진 하루 되시길 바라요!",
            "바이": "Bye! 👋 좋은 쇼핑 되시고 또 만나요!",
            
            # 일상 대화
            "심심해": "그럼 재미있는 패션 이야기를 해볼까요? 😄 요즘 트렌드나 관심 있는 스타일이 있나요?",
            "지루해": "패션으로 기분 전환해봐요! ✨ 새로운 스타일에 도전해보는 건 어떨까요?",
            "우울해": "옷 쇼핑으로 기분 전환해봐요! 😊 예쁜 옷 보면 기분이 좋아져요. 어떤 스타일을 좋아하세요?",
            
            # 상태 및 컨디션
            "피곤해": "편안한 옷을 추천해드릴까요? 😴 집에서 입기 좋은 편안한 옷들이 있어요!",
            "추워": "따뜻한 옷을 찾아드릴게요! 🧥 어떤 종류의 아우터를 원하시나요?",
            "더워": "시원한 여름 옷을 추천해드릴게요! 🌞 어떤 스타일을 선호하시나요?"
        }
        
        # 의류 관련 키워드
        self.clothing_keywords = [
            "옷", "의류", "패션", "스타일", "셔츠", "바지", "치마", "드레스", 
            "코트", "재킷", "니트", "후드", "티셔츠", "청바지", "운동복", 
            "정장", "데이트", "면접", "파티", "결혼식", "졸업식"
        ]
    
    def process_general_request(self, user_input: str, extracted_info: Dict,
                              context_summaries: Optional[List[str]] = None) -> GeneralAgentResult:
        """
        일반적인 대화 요청 처리
        
        Args:
            user_input: 사용자 입력
            extracted_info: 추출된 정보
            context_summaries: 이전 대화 요약들
        
        Returns:
            GeneralAgentResult: 일반 대화 결과
        """
        print(f"=== General Agent 시작 ===")
        print(f"사용자 입력: {user_input}")
        
        try:
            user_input_lower = safe_lower(user_input)
            
            # 1. 미리 정의된 응답 확인
            predefined_response = self._check_predefined_responses(user_input_lower)
            if predefined_response:
                return GeneralAgentResult(
                    success=True,
                    message=predefined_response,
                    products=[],
                    metadata={"response_type": "predefined", "agent_type": "general"}
                )
            
            # 2. LLM을 사용한 자연스러운 대화 처리
            response = self._generate_intelligent_response(user_input, context_summaries)
            
            # 3. 의류 관련 질문인지 확인하여 안내 추가
            has_clothing_context = self._has_clothing_context(user_input_lower)
            if not has_clothing_context and not any(keyword in user_input_lower for keyword in ["안녕", "감사", "고마워", "좋아"]):
                # 의류와 관련 없는 질문에는 의류 추천 안내 추가
                response += "\n\n💡 의류나 패션 관련 질문이 있으시면 언제든 말씀해주세요!"
            
            return GeneralAgentResult(
                success=True,
                message=response,
                products=[],
                metadata={"response_type": "clothing_related", "agent_type": "general"}
            )
            
        except Exception as e:
            print(f"General Agent 오류: {e}")
            return GeneralAgentResult(
                success=True,
                message="안녕하세요! 의류 추천을 도와드릴게요. 어떤 옷을 찾고 계신가요? 👕",
                products=[],
                metadata={"error": str(e), "agent_type": "general"}
            )
    
    def _check_predefined_responses(self, user_input_lower: str) -> Optional[str]:
        """미리 정의된 응답 확인"""
        for keyword, response in self.predefined_responses.items():
            if keyword in user_input_lower:
                return response
        return None
    
    def _has_clothing_context(self, user_input_lower: str) -> bool:
        """의류 관련 컨텍스트 확인"""
        return any(keyword in user_input_lower for keyword in self.clothing_keywords)
    
    def _get_non_clothing_response(self) -> str:
        """의류와 관련 없는 질문에 대한 응답"""
        return """저는 의류 추천 전문 챗봇이에요! 👗

의류나 패션에 관한 질문을 해주시면 도움을 드릴 수 있어요.

**예시:**
• '파란색 셔츠 추천해줘'
• '데이트룩 추천해줘'
• '면접복 추천해줘'
• '오늘 날씨에 맞는 옷 추천해줘'

어떤 옷을 찾고 계신가요? 😊"""
    
    def _get_basic_clothing_response(self) -> str:
        """기본 의류 관련 응답"""
        return """안녕하세요! 의류 추천을 도와드릴게요. 👕

구체적으로 말씀해주시면 더 정확한 추천을 드릴 수 있어요!

**추천 방법:**
• **구체적 검색**: '파란색 셔츠', '청바지' 등
• **상황별 추천**: '데이트룩', '면접복', '파티룩' 등
• **날씨별 추천**: '오늘 날씨에 맞는 옷' 등

어떤 스타일을 찾고 계신가요? ✨"""
    
    def _generate_intelligent_response(self, user_input: str, context_summaries: Optional[List[str]] = None) -> str:
        """LLM을 사용한 지능형 응답 생성"""
        try:
            # 컨텍스트 정보 구성
            context_info = ""
            if context_summaries:
                recent_context = " | ".join(context_summaries[-3:])
                context_info = f"이전 대화 요약: {recent_context}"
            
            system_prompt = f"""당신은 친근하고 도움이 되는 의류 추천 챗봇입니다.
사용자의 다양한 질문에 자연스럽고 따뜻하게 응답해주세요.

{context_info}

응답 가이드라인:
1. 친근하고 자연스러운 대화체 사용
2. 사용자의 감정과 상황 공감
3. 가능하면 의류/패션과 연결하여 도움 제안
4. 이모지를 적절히 사용해서 친근함 표현
5. 간결하면서도 따뜻한 응답 (2-4줄)
6. 의류와 전혀 관련 없는 질문도 자연스럽게 응답

특별 지침:
- 일상 대화, 감정 표현, 상태 문의 등에 자연스럽게 응답
- 가능한 경우 패션/의류 추천으로 자연스럽게 연결
- 부정적 감정에는 위로와 격려 제공"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"사용자 입력: {user_input}"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=250
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"지능형 응답 생성 오류: {e}")
            return self._get_basic_clothing_response()
    
    def _generate_contextual_response(self, user_input: str, context_summaries: List[str]) -> str:
        """컨텍스트를 활용한 응답 생성 (호환성 유지)"""
        return self._generate_intelligent_response(user_input, context_summaries)
    
    def is_greeting(self, user_input: str) -> bool:
        """인사말인지 확인"""
        greetings = ["안녕", "하이", "hello", "hi", "헬로", "좋은아침", "좋은오후", "좋은저녁"]
        user_input_lower = safe_lower(user_input)
        return any(greeting in user_input_lower for greeting in greetings)
    
    def is_thanks(self, user_input: str) -> bool:
        """감사 표현인지 확인"""
        thanks_words = ["감사", "고마워", "고맙", "땡큐", "thank", "thx"]
        user_input_lower = safe_lower(user_input)
        return any(thanks in user_input_lower for thanks in thanks_words)
    
    def is_farewell(self, user_input: str) -> bool:
        """작별 인사인지 확인"""
        farewell_words = ["안녕", "잘가", "굿바이", "bye", "goodbye", "빠이", "종료"]
        user_input_lower = safe_lower(user_input)
        return any(farewell in user_input_lower for farewell in farewell_words)
    
    def generate_farewell_response(self) -> str:
        """작별 인사 응답 생성"""
        return "좋은 하루 되세요! 😊 또 필요하실 때 언제든 찾아주세요. 안녕히 가세요! 👋"
