import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
import os
from dotenv import load_dotenv
from utils.safe_utils import safe_lower

load_dotenv()

@dataclass
class ChatMessage:
    role: str  # 'user' or 'assistant'
    content: str

@dataclass
class IntentResult:
    intent: str  # 'search', 'conversation', 'general'
    confidence: float
    extracted_info: Dict
    original_query: str

class IntentAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
        
    def classify_intent(self, user_input: str, chat_history: List[ChatMessage]) -> IntentResult:
        """사용자 입력의 의도를 분류합니다."""
        
        # 대화 컨텍스트 구성
        context = self._build_context(chat_history)
        
        system_prompt = """당신은 의류 추천 챗봇의 의도 분류 전문가입니다.
사용자의 입력을 분석하여 다음 중 하나로 분류해주세요:

1. search: 구체적인 상품 검색 요청 (색상, 종류, 브랜드 등 명시)
   예시: "파란색 셔츠 추천해줘", "검은색 청바지 찾아줘", "티셔츠 추천해줘"

2. conversation: 상황 기반 대화형 추천 요청
   예시: "여름 데이트룩 추천해줘", "면접복 추천해줘", "파티에 입을 옷 추천해줘"

3. general: 일반적인 대화나 질문
   예시: "안녕하세요", "도움말", "감사합니다"

응답은 다음 JSON 형식으로만 해주세요:
{
    "intent": "search|conversation|general",
    "confidence": 0.0-1.0,
    "extracted_info": {
        "colors": ["색상들"],
        "categories": ["카테고리들"],
        "situations": ["상황들"],
        "styles": ["스타일들"],
        "keywords": ["키워드들"]
    }
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"대화 컨텍스트:\n{context}\n\n현재 입력: {user_input}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            return IntentResult(
                intent=result["intent"],
                confidence=result["confidence"],
                extracted_info=result["extracted_info"],
                original_query=user_input
            )
            
        except Exception as e:
            print(f"의도 분류 오류: {e}")
            # 기본값 반환
            return IntentResult(
                intent="search",
                confidence=0.5,
                extracted_info={"keywords": [user_input]},
                original_query=user_input
            )
    
    def _build_context(self, chat_history: List[ChatMessage]) -> str:
        """채팅 히스토리를 컨텍스트로 변환합니다."""
        if not chat_history:
            return "대화 기록이 없습니다."
        
        context_parts = []
        for msg in chat_history[-6:]:  # 최근 6개 메시지만 사용
            role = "사용자" if msg.role == "user" else "챗봇"
            context_parts.append(f"{role}: {msg.content}")
        
        return "\n".join(context_parts)

def analyze_user_intent(user_input: str) -> dict:
    """사용자 의도 분석 (기존 함수 유지)"""
    # None 값 안전 처리
    user_input_lower = safe_lower(user_input)
    
    # 상황별 키워드
    situations = {
        "졸업식": ["졸업식", "졸업", "학위수여식"],
        "결혼식": ["결혼식", "웨딩", "피로연"],
        "데이트": ["데이트", "소개팅", "만남"],
        "면접": ["면접", "취업", "입사", "회사"],
        "파티": ["파티", "클럽", "놀기"],
        "외출": ["외출", "나들이", "쇼핑"],
        "동창회": ["동창회", "모임"]
    }
    
    # 직접 필터링 키워드
    direct_keywords = ["티셔츠", "셔츠", "바지", "청바지", "니트", "후드", 
                      "빨간", "파란", "검은", "흰", "회색", "red", "blue", "black"]
    
    # 상황별 매칭 확인
    for situation, keywords in situations.items():
        if any(keyword in user_input_lower for keyword in keywords):
            return {
                "type": "SITUATION",
                "situation": situation,
                "original_input": user_input
            }
    
    # 직접 필터링 매칭 확인
    if any(keyword in user_input_lower for keyword in direct_keywords):
        return {
            "type": "FILTERING", 
            "original_input": user_input
        }
    
    # 기본값은 일반 검색
    return {
        "type": "FILTERING",
        "original_input": user_input
    }

def analyze_user_intent_with_context(user_input: str, conversation_context: str = "") -> dict:
    """사용자 의도 분석 (대화 컨텍스트 고려)"""
    # None 값 안전 처리
    user_input_lower = safe_lower(user_input)
    context_lower = safe_lower(conversation_context)
    
    # 컨텍스트에서 이전 대화 내용 분석
    context_keywords = []
    if conversation_context:
        # 이전 대화에서 언급된 키워드들 추출
        context_keywords = extract_keywords_from_context(conversation_context)
        print(f"컨텍스트 키워드: {context_keywords}")
    
    # 상황별 키워드
    situations = {
        "졸업식": ["졸업식", "졸업", "학위수여식"],
        "결혼식": ["결혼식", "웨딩", "피로연"],
        "데이트": ["데이트", "소개팅", "만남"],
        "면접": ["면접", "취업", "입사", "회사"],
        "파티": ["파티", "클럽", "놀기"],
        "외출": ["외출", "나들이", "쇼핑"],
        "동창회": ["동창회", "모임"]
    }
    
    # 직접 필터링 키워드
    direct_keywords = ["티셔츠", "셔츠", "바지", "청바지", "니트", "후드", 
                      "빨간", "파란", "검은", "흰", "회색", "red", "blue", "black"]
    
    # 컨텍스트와 현재 입력을 모두 고려한 상황별 매칭
    for situation, keywords in situations.items():
        # 현재 입력에서 키워드 확인
        current_match = any(keyword in user_input_lower for keyword in keywords)
        # 컨텍스트에서 키워드 확인
        context_match = any(keyword in context_lower for keyword in keywords)
        
        if current_match or context_match:
            return {
                "type": "SITUATION",
                "situation": situation,
                "original_input": user_input,
                "context_used": context_match
            }
    
    # 직접 필터링 매칭 확인
    if any(keyword in user_input_lower for keyword in direct_keywords):
        return {
            "type": "FILTERING", 
            "original_input": user_input
        }
    
    # 기본값은 일반 검색
    return {
        "type": "FILTERING",
        "original_input": user_input
    }

def extract_keywords_from_context(context: str) -> List[str]:
    """컨텍스트에서 키워드를 추출합니다."""
    keywords = []
    
    # 색상 키워드
    color_keywords = ["빨간", "파란", "검은", "흰", "회색", "red", "blue", "black", "white", "gray"]
    for color in color_keywords:
        if color in safe_lower(context):
            keywords.append(color)
    
    # 의류 키워드
    clothing_keywords = ["티셔츠", "셔츠", "바지", "청바지", "니트", "후드", "shirt", "pants", "jeans"]
    for clothing in clothing_keywords:
        if clothing in safe_lower(context):
            keywords.append(clothing)
    
    return keywords
