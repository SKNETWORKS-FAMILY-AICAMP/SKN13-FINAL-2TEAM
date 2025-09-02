"""
통합 서머리 에이전트
LLM 최종 답변까지 포함한 완전한 Q/A 요약 시스템
"""
import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

@dataclass
class UnifiedSummaryResult:
    """통합 서머리 결과"""
    success: bool
    summary_text: str
    action_taken: str  # "created", "updated", "replaced", "kept"
    confidence: float
    metadata: Dict
    is_new_summary: bool
    contains_llm_response: bool

class UnifiedSummaryAgent:
    """
    통합 서머리 에이전트
    - 사용자 질문 + LLM 최종 답변을 모두 포함한 요약 생성
    - 기존 요약과의 지능적 병합/업데이트
    - 단일 에이전트로 모든 요약 기능 통합
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    
    def process_complete_qa_summary(self, user_input: str, llm_final_response: str, 
                                  existing_summary: Optional[str] = None) -> UnifiedSummaryResult:
        """
        완전한 Q/A 요약 처리 (사용자 입력 + LLM 최종 답변)
        
        Args:
            user_input: 사용자 입력
            llm_final_response: LLM의 최종 답변 (상품 추천 포함)
            existing_summary: 기존 요약 (있는 경우)
        
        Returns:
            UnifiedSummaryResult: 통합 요약 결과
        """
        print(f"=== 통합 서머리 에이전트 시작 ===")
        print(f"사용자 입력: {user_input[:50]}...")
        print(f"LLM 답변: {llm_final_response[:100]}...")
        print(f"기존 요약: {existing_summary[:50] if existing_summary else 'None'}...")
        
        try:
            if existing_summary:
                # 기존 요약이 있으면 업데이트 처리
                return self._update_existing_summary(user_input, llm_final_response, existing_summary)
            else:
                # 기존 요약이 없으면 새로 생성
                return self._create_new_summary(user_input, llm_final_response)
                
        except Exception as e:
            print(f"통합 서머리 에이전트 오류: {e}")
            # 오류 시 fallback 요약 생성
            fallback_summary = self._create_fallback_summary(user_input, llm_final_response)
            return UnifiedSummaryResult(
                success=False,
                summary_text=fallback_summary,
                action_taken="error_fallback",
                confidence=0.0,
                metadata={"error": str(e), "agent_type": "unified_summary"},
                is_new_summary=True,
                contains_llm_response=True
            )
    
    def _create_new_summary(self, user_input: str, llm_response: str) -> UnifiedSummaryResult:
        """새로운 완전한 요약 생성"""
        
        system_prompt = """당신은 의류 추천 챗봇의 대화 요약 전문가입니다.
사용자의 질문과 챗봇의 최종 응답을 종합하여 완전한 요약을 생성해주세요.

요약에 포함할 요소:
1. 사용자가 원한 것 (의도, 조건, 상황)
2. 챗봇이 제공한 정보/추천 (상품, 조언, 정보)
3. 중요한 키워드 (색상, 브랜드, 스타일, 가격대)
4. 추천 결과 (몇 개 추천, 어떤 특징)

가이드라인:
- 120자 내외로 간결하면서도 완전하게
- 사용자 니즈와 봇 응답을 모두 포함
- 향후 참조에 유용한 구체적 정보 포함
- 자연스러운 한국어
- **추천결과에 대한 내용은 해당 사항 변경하지않고 원문 그대로 저장해주세요**

예시:
"파란색 캐주얼 셔츠 요청 → 3개 브랜드(유니클로, 무지 등) 추천, 2-3만원대, 면 소재 위주"
"데이트룩 상담 → 로맨틱 스타일 상하의 세트 추천, 5-7만원대, 봄 시즌 적합"
"""

        user_prompt = f"""사용자 질문: {user_input}

챗봇 최종 응답: {llm_response}

위 Q/A를 완전히 요약해주세요."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            
            summary = response.choices[0].message.content.strip()
            print(f"새 요약 생성 완료: {summary}")
            
            return UnifiedSummaryResult(
                success=True,
                summary_text=summary,
                action_taken="created",
                confidence=0.9,
                metadata={
                    "agent_type": "unified_summary",
                    "input_length": len(user_input),
                    "response_length": len(llm_response),
                    "summary_length": len(summary)
                },
                is_new_summary=True,
                contains_llm_response=True
            )
            
        except Exception as e:
            print(f"새 요약 생성 오류: {e}")
            raise
    
    def _update_existing_summary(self, user_input: str, llm_response: str, 
                               existing_summary: str) -> UnifiedSummaryResult:
        """기존 요약 업데이트"""
        
        system_prompt = """당신은 대화 요약 업데이트 전문가입니다.
기존 요약과 새로운 Q/A를 분석하여 최적의 업데이트 방식을 결정하고 실행해주세요.

업데이트 방식:
1. **kept**: 새로운 Q/A가 기존 요약과 거의 중복되거나 덜 중요한 경우
2. **updated**: 기존 요약에 새로운 정보를 추가/수정
3. **replaced**: 새로운 Q/A가 더 중요하거나 완전히 다른 주제인 경우
4. **merged**: 기존과 새로운 정보를 자연스럽게 병합

중요한 고려사항:
- 의류 추천에서는 구체적인 조건(색상, 브랜드, 가격)이 중요
- 후속 질문이나 추가 요청도 의미있는 정보
- 사용자의 선호도 변화나 새로운 니즈 반영
- 최대 150자 내외 유지
**추천결과에 대한 내용은 해당 사항 변경하지않고 원문 그대로 저장해주세요**

JSON 형식으로 응답:
{
    "action": "kept|updated|replaced|merged",
    "summary": "최종 요약 텍스트",
    "confidence": 0.0-1.0,
    "reasoning": "결정 이유 (간단히)"
}"""

        user_prompt = f"""기존 요약: {existing_summary}

새로운 Q/A:
질문: {user_input}
응답: {llm_response}

위 정보를 바탕으로 요약을 업데이트해주세요."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=350
            )
            
            result_text = response.choices[0].message.content.strip()
            result = json.loads(result_text)
            
            print(f"요약 업데이트: {result['action']} (신뢰도: {result.get('confidence', 0.8)})")
            print(f"최종 요약: {result['summary']}")
            
            return UnifiedSummaryResult(
                success=True,
                summary_text=result["summary"],
                action_taken=result["action"],
                confidence=result.get("confidence", 0.8),
                metadata={
                    "agent_type": "unified_summary",
                    "reasoning": result.get("reasoning", ""),
                    "original_length": len(existing_summary),
                    "new_length": len(result["summary"]),
                    "input_length": len(user_input),
                    "response_length": len(llm_response)
                },
                is_new_summary=False,
                contains_llm_response=True
            )
            
        except Exception as e:
            print(f"기존 요약 업데이트 오류: {e}")
            raise
    
    def _create_fallback_summary(self, user_input: str, llm_response: str) -> str:
        """오류 시 간단한 fallback 요약 생성"""
        # 키워드 추출 시도
        user_keywords = self._extract_keywords(user_input)
        response_keywords = self._extract_keywords(llm_response[:200])
        
        if user_keywords and response_keywords:
            return f"{user_keywords} 요청 → {response_keywords} 응답"
        else:
            return f"Q: {user_input[:30]}... → A: {llm_response[:30]}..."
    
    def _extract_keywords(self, text: str) -> str:
        """간단한 키워드 추출"""
        # 의류 관련 주요 키워드들
        clothing_keywords = [
            "셔츠", "티셔츠", "바지", "청바지", "스커트", "니트", "후드", "맨투맨",
            "원피스", "재킷", "코트", "신발", "가방", "악세사리"
        ]
        
        color_keywords = [
            "빨간", "파란", "검은", "흰", "노란", "초록", "분홍", "보라", "회색", "갈색"
        ]
        
        style_keywords = [
            "캐주얼", "정장", "스포츠", "데이트", "면접", "여행", "파티", "로맨틱"
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in clothing_keywords + color_keywords + style_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return ", ".join(found_keywords[:3]) if found_keywords else ""
    
    def extract_summary_insights(self, summary: str) -> Dict:
        """요약에서 인사이트 추출 (향후 개인화에 활용)"""
        insights = {
            "preferred_colors": [],
            "preferred_styles": [],
            "price_range": None,
            "brands_mentioned": [],
            "categories": []
        }
        
        # 간단한 패턴 매칭으로 인사이트 추출
        summary_lower = summary.lower()
        
        # 색상 추출
        colors = ["빨간", "파란", "검은", "흰", "노란", "초록", "분홍", "보라", "회색", "갈색"]
        for color in colors:
            if color in summary_lower:
                insights["preferred_colors"].append(color)
        
        # 스타일 추출
        styles = ["캐주얼", "정장", "스포츠", "로맨틱", "미니멀"]
        for style in styles:
            if style in summary_lower:
                insights["preferred_styles"].append(style)
        
        # 브랜드 추출 (일반적인 브랜드들)
        brands = ["유니클로", "무지", "자라", "h&m", "스파오"]
        for brand in brands:
            if brand in summary_lower:
                insights["brands_mentioned"].append(brand)
        
        return insights
    
    def generate_session_overview(self, qa_summaries: List[str]) -> str:
        """여러 Q/A 요약을 바탕으로 세션 전체 개요 생성"""
        if not qa_summaries:
            return "대화 내용 없음"
        
        if len(qa_summaries) == 1:
            return qa_summaries[0]
        
        system_prompt = """당신은 의류 추천 세션 분석 전문가입니다.
여러 Q/A 요약들을 종합하여 전체 세션의 특징과 패턴을 설명해주세요.

세션 개요에 포함할 요소:
1. 사용자의 주요 관심사나 쇼핑 목적
2. 선호하는 스타일, 색상, 브랜드 패턴
3. 가격대나 품질에 대한 관심도
4. 대화의 진행 방향 (탐색→결정, 비교 중심 등)

150자 내외로 간결하게 작성해주세요.

예시:
"파란색 상의 중심 쇼핑 - 캐주얼에서 정장까지 다양한 스타일 탐색, 브랜드별 특징 비교에 관심"
"데이트룩 전문 상담 - 로맨틱 스타일 선호, 상하의 조화 중시, 3-5만원대 예산 설정"
"""

        summaries_text = "\n".join([f"- {summary}" for summary in qa_summaries])
        user_prompt = f"""Q/A 요약들:
{summaries_text}

위 요약들을 종합한 세션 개요를 생성해주세요."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            overview = response.choices[0].message.content.strip()
            print(f"세션 개요 생성: {overview}")
            return overview
            
        except Exception as e:
            print(f"세션 개요 생성 오류: {e}")
            return f"총 {len(qa_summaries)}개 대화 - 의류 추천 상담 세션"
