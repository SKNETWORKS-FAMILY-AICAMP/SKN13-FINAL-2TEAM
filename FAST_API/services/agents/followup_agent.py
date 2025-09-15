"""
FollowUp Agent (간소화 버전)
이전 Q/A 데이터를 기반으로 후속 질문을 처리하는 에이전트
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

@dataclass
class FollowUpAgentResult:
    """FollowUp Agent 결과"""
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

class FollowUpAgent:
    """후속 질문 처리 에이전트"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"
    
    def is_follow_up_question(self, user_input: str, db=None, user_id: int = None) -> bool:
        """후속 질문인지 판단"""
        print(f"=== FollowUp Agent - 후속 질문 체크 ===")
        print(f"입력: {user_input}")
        
        # 후속 질문 키워드들
        follow_up_keywords = [
            "저거", "그거", "위에", "중에", "가장", "제일", "첫번째", "두번째", "세번째", "마지막",
            "싸", "비싸", "저렴", "비용", "가격", "얼마", "사이즈", "색깔", "어떤", "좋을까",
            "추천", "선택", "고르", "더", "다른", "또", "어느", "몇번째"
        ]
        
        user_lower = user_input.lower()
        matched_keywords = [kw for kw in follow_up_keywords if kw in user_lower]
        
        if len(matched_keywords) == 0:
            print("후속 질문 키워드가 없음")
            return False
        
        # 키워드가 있으면 최근 추천 확인 (선택사항)
        if db and user_id:
            has_recent_recs = self._check_recent_recommendations(db, user_id)
            print(f"매칭된 키워드: {matched_keywords}")
            print(f"최근 추천 있음: {has_recent_recs}")
            return has_recent_recs
        else:
            # db/user_id가 없으면 키워드만으로 판단
            print(f"매칭된 키워드: {matched_keywords}")
            print("후속 질문 판정: True (키워드 기반)")
            return True
    
    def process_follow_up_question(self, user_input: str, db, user_id: int, session_id: str = None, search_agent=None, available_products=None) -> FollowUpAgentResult:
        """
        후속 질문 처리 (간소화 버전)
        
        Args:
            user_input: 사용자 입력
            db: 데이터베이스 세션
            user_id: 사용자 ID
            session_id: 현재 세션 ID (선택사항)
        
        Returns:
            FollowUpAgentResult: 후속 질문 처리 결과
        """
        print(f"=== FollowUp Agent 시작 (간소화) ===")
        print(f"질문: {user_input}, 세션: {session_id}, 사용자: {user_id}")
        
        try:
            print(f"🔍 팔로우업 프로세스 시작")
            print(f"🔍 매개변수: session_id={session_id}, user_id={user_id}")
            
            # 특정 세션의 최근 Q/A 데이터 불러오기
            print(f"🔍 Q/A 데이터 로드 시도...")
            recent_qa_data = self._get_recent_qa_data(db, user_id, session_id)
            
            print(f"🔍 Q/A 데이터 로드 결과: {len(recent_qa_data)}개")
            
            if not recent_qa_data:
                error_msg = f"❌ 세션 {session_id}에서 최근 대화 내용을 찾을 수 없습니다." if session_id else "❌ 최근 대화 내용을 찾을 수 없습니다."
                error_msg += " 먼저 상품을 추천받은 후 후속 질문을 해주세요."
                
                print(f"🔍 Q/A 데이터 없음 - 오류 반환")
                
                return FollowUpAgentResult(
                    success=False,
                    message=error_msg,
                    products=[],
                    metadata={"error": "no_recent_qa", "agent_type": "followup", "session_id": session_id}
                )
            
            # LLM이 검색이 필요한지 판단하고 검색 에이전트로 연결
            if search_agent and available_products:
                search_needed = self._check_if_search_needed(user_input, recent_qa_data)
                if search_needed:
                    return self._handle_llm_guided_search(user_input, recent_qa_data, search_agent, available_products)
            
            # LLM을 사용해 후속 질문 처리 (답변 + 상품 정보 함께)
            print(f"🔍 LLM 답변 생성 시작...")
            answer, related_products = self._generate_followup_answer_with_llm(user_input, recent_qa_data)
            
            print(f"🔍 LLM 답변 생성 완료: {answer[:50]}...")
            print(f"🔍 관련 상품: {len(related_products)}개")
            
            result = FollowUpAgentResult(
                success=True,
                message=answer,
                products=related_products,
                metadata={"follow_up": True, "agent_type": "followup", "qa_count": len(recent_qa_data), "products_count": len(related_products)}
            )
            
            print(f"🔍 팔로우업 결과 반환: success={result.success}")
            return result
            
        except Exception as e:
            print(f"FollowUp Agent 오류: {e}")
            import traceback
            traceback.print_exc()
            
            return FollowUpAgentResult(
                success=False,
                message="후속 질문을 처리하는 중 오류가 발생했습니다. 다시 시도해주세요.",
                products=[],
                metadata={"error": str(e), "agent_type": "followup"}
            )
    
    def _get_recent_qa_data(self, db, user_id: int, session_id: str = None) -> List[Dict]:
        """특정 세션의 최근 Q/A 데이터 불러오기"""
        try:
            if session_id:
                # 특정 세션의 메시지들 가져오기
                from crud.chat_crud import get_session_messages
                
                all_messages = get_session_messages(db, session_id, user_id)
                # 최근 10개 메시지만 사용 (토큰 절약)
                messages_data = all_messages[-10:] if len(all_messages) > 10 else all_messages
            else:
                # 전체 사용자 히스토리에서 가져오기 (fallback)
                from crud.chat_crud import get_user_chat_history
                recent_messages = get_user_chat_history(db, user_id, limit=10)
                messages_data = [
                    {
                        "id": msg.id,
                        "type": msg.message_type,
                        "text": msg.text,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None
                    }
                    for msg in recent_messages
                ]
            
            qa_pairs = []
            user_msg = None
            
            # 메시지들을 시간순으로 정렬 (오래된 것부터)
            messages_data.sort(key=lambda x: x.get('created_at', ''), reverse=False)
            
            # 연속된 유저-봇 메시지를 Q/A 쌍으로 구성
            for i, msg_data in enumerate(messages_data):
                msg_type = msg_data.get('type')
                msg_text = msg_data.get('text', '')
                
                if msg_type == "user":
                    user_msg = msg_text
                elif msg_type == "bot" and user_msg:
                    qa_pair = {
                        "question": user_msg,
                        "answer": msg_text,
                        "created_at": msg_data.get('created_at')
                    }
                    
                    # 상품 정보가 있으면 추가
                    if msg_data.get('products_data') and len(msg_data['products_data']) > 0:
                        qa_pair['products_data'] = msg_data['products_data']
                    
                    qa_pairs.append(qa_pair)
                    user_msg = None  # 사용된 유저 메시지 초기화
            
            # 최근 1개 Q/A만 사용 (가장 최근 것)
            recent_qa = qa_pairs[-1:] if len(qa_pairs) >= 1 else qa_pairs
            
            return recent_qa
            
        except Exception as e:
            print(f"Q/A 데이터 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _generate_followup_answer_with_llm(self, user_input: str, recent_qa_data: List[Dict]) -> tuple[str, List[Dict]]:
        """LLM을 사용해 후속 질문에 대한 답변 생성"""
        
        # 최근 Q/A 데이터를 텍스트로 구성
        qa_context = ""
        products_info = ""
        
        for i, qa in enumerate(recent_qa_data, 1):
            qa_context += f"Q{i}: {qa['question']}\n"
            qa_context += f"A{i}: {qa['answer'][:300]}...\n\n"  # 답변은 300자로 제한
            
            # 상품 정보가 있으면 추가
            if qa.get('products_data') and len(qa['products_data']) > 0:
                products_info += f"Q{i}에서 추천된 상품들:\n"
                for j, product in enumerate(qa['products_data'][:3], 1):  # 최대 3개만
                    product_name = product.get('상품명', '상품명 없음')
                    brand = product.get('한글브랜드명', '브랜드 없음')
                    price = product.get('원가', product.get('가격', 0))
                    product_link = product.get('상품링크', '')
                    site_name = product.get('사이트명', '')
                    image_url = product.get('사진', product.get('이미지URL', ''))
                    products_info += f"  {j}. {product_name} ({brand}) - {price:,}원\n"
                    products_info += f"      링크: {product_link}\n"
                    products_info += f"      사이트: {site_name}\n"
                    products_info += f"      이미지: {image_url}\n"
                products_info += "\n"
        
        system_prompt = """당신은 의류 추천 챗봇의 후속 질문 전문가입니다.
사용자가 이전 대화 내용에 대해 후속 질문을 했습니다.

역할:
1. 이전 Q/A 내용과 추천된 상품 정보를 기반으로 사용자의 후속 질문에 답변
2. 가격, 브랜드, 스타일 등을 비교/분석하여 도움되는 정보 제공
3. 구체적이고 실용적인 조언 제공
4. 관련 상품들을 함께 반환
5. json 형식도 추천해준 상품갯수에 맞춰서 반환(추가로 더하지말고 그대로 반환)

답변 스타일:
- 친근하고 도움이 되는 톤
- 이전 대화 내용과 상품 정보를 정확히 참조
- 가격 비교, 브랜드 정보, 상품 순서 등을 명확하게 제시
- "가장 싼 거", "첫 번째", "브랜드" 등의 질문에 구체적으로 답변
- 추가 질문이나 선택에 도움되는 정보 포함


**중요**: 반드시 순수 JSON만 반환하세요. 마크다운 코드 블록(```json)이나 다른 텍스트 없이 JSON만 출력하세요.

응답 예시:
{
    "answer": "가장 저렴한 상품은...",
    "related_products": [
        {
            "상품코드": "123456",
            "상품명": "상품명",
            "한글브랜드명": "브랜드명",
            "원가": 50000,
            "사진": "이미지URL",
            "상품링크": "링크URL"
        }
    ]
}

관련 상품 선택 기준:
- **반드시 가장 최근 Q/A에서 추천된 상품들만 사용하세요**
- 질문의 의도를 정확히 파악하여 필요한 상품만 선택
- "둘 중 뭐가 나아?" 같은 비교 질문이면 1개만 선택
- "가장 싼 거" 질문이면 1개만 선택 (가장 저렴한 것)
- "첫 번째" 질문이면 1개만 선택 (첫 번째 상품)
- "브랜드" 질문이면 해당 브랜드 상품 1-2개 선택
- 일반적인 후속 질문이면 관련 상품 1-3개 선택 (최대 3개)
- **중요: 오래된 Q/A의 상품은 절대 사용하지 마세요. 최근 Q/A의 상품만 사용하세요.**

**중요**: 상품 정보에서 제공된 실제 링크, 사이트명, 이미지 URL을 그대로 사용하세요.
가짜 링크나 "example.com" 같은 더미 링크를 만들지 마세요."""

        user_prompt = f"""
사용자 후속 질문: {user_input}

최근 대화 내용:
{qa_context}

{products_info if products_info else ""}


위 대화 내용과 상품 정보를 바탕으로 사용자의 후속 질문에 답변해주세요."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            raw_response = response.choices[0].message.content.strip()
            print(f"LLM 원본 응답: {raw_response[:100]}...")
            
            # LLM 응답이 JSON인지 확인
            import json
            try:
                # 마크다운 코드 블록 제거
                cleaned_response = raw_response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]  # ```json 제거
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # ``` 제거
                cleaned_response = cleaned_response.strip()
                
                result = json.loads(cleaned_response)
                # JSON 파싱 성공 시 상품 정보 포함 응답
                answer = result.get("answer", "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다.")
                related_products = result.get("related_products", [])
                
                # 챗봇 카드 호환성을 위해 필드 매핑 (강화된 버전)
                for product in related_products:
                    print(f"🔍 원본 상품 데이터: {product}")
                    
                    # 가격 필드 매핑 (챗봇 JavaScript에서 '가격' 필드를 사용)
                    if '원가' in product:
                        product['가격'] = product['원가']  # 무조건 가격 필드 추가
                        print(f"🔍 가격 필드 매핑: 원가={product['원가']} → 가격={product['가격']}")
                    
                    # 이미지 URL 필드 매핑 (여러 필드명 지원)
                    image_url = product.get('사진') or product.get('이미지URL') or product.get('대표이미지URL') or ''
                    if image_url:
                        product['사진'] = image_url
                        product['이미지URL'] = image_url
                        product['대표이미지URL'] = image_url
                        print(f"🔍 이미지 URL 매핑: {image_url}")
                    
                    # 챗봇 JavaScript 호환성을 위한 추가 필드 매핑
                    if '상품코드' in product:
                        product['product_id'] = product['상품코드']
                        print(f"🔍 상품코드 매핑: {product['상품코드']}")
                    if '상품링크' in product:
                        product['product_link'] = product['상품링크']
                    if '상품명' in product:
                        product['product_name'] = product['상품명']
                    if '한글브랜드명' in product:
                        product['brand_name'] = product['한글브랜드명']
                    
                    print(f"🔍 매핑 후 상품 데이터: {product}")
                
                print(f"LLM JSON 답변 생성 완료: {answer[:50]}...")
                print(f"관련 상품 {len(related_products)}개 반환")
                
                return answer, related_products
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 일반 텍스트 응답으로 처리
                print(f"LLM 일반 텍스트 답변 생성 완료: {raw_response[:50]}...")
                return raw_response, []
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다.", []
        except Exception as e:
            print(f"LLM 답변 생성 오류: {e}")
            return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다.", []

    def _check_if_search_needed(self, user_input: str, recent_qa_data: List[Dict]) -> bool:
        """LLM이 검색이 필요한지 판단합니다."""
        try:
            # 최근 Q/A 데이터를 간단히 요약
            recent_context = ""
            if recent_qa_data:
                latest_qa = recent_qa_data[-1]
                recent_context = f"최근 추천: {latest_qa.get('products_data', [{}])[0].get('상품명', '상품명 없음')} (브랜드: {latest_qa.get('products_data', [{}])[0].get('한글브랜드명', '브랜드 없음')})"
            
            prompt = f"""사용자의 질문을 분석하여 새로운 상품 검색이 필요한지 판단해주세요.

사용자 질문: {user_input}
{recent_context}

판단 기준:
1. 기존 추천 상품들 중에서 선택/비교하는 질문이면 "false"
2. 새로운 카테고리나 다른 상품을 찾는 질문이면 "true"

예시:
- "둘 중 뭐가 나아?" → false (기존 상품 선택)
- "가장 싼 거" → false (기존 상품 중 선택)
- "저거랑 어울리는 상의 추천해줘" → true (새로운 상의 검색 필요)
- "흰색 블라우스 보여줘" → true (새로운 상품 검색 필요)
- "상의 보여줘" → true (새로운 상품 검색 필요)

답변: true 또는 false만"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            result = response.choices[0].message.content.strip().lower()
            return "true" in result
            
        except Exception as e:
            print(f"검색 필요성 판단 오류: {e}")
            return False
    
    def _handle_llm_guided_search(self, user_input: str, recent_qa_data: List[Dict], search_agent, available_products) -> FollowUpAgentResult:
        """LLM이 생성한 검색 쿼리로 검색 에이전트를 실행합니다."""
        try:
            print(f"🔍 LLM 가이드 검색 시작: {user_input}")
            
            # LLM이 검색 쿼리 생성
            search_query = self._generate_search_query_with_llm(user_input, recent_qa_data)
            
            if not search_query:
                # 검색 쿼리 생성 실패 시 기존 팔로우업 처리
                print(f"🔍 검색 쿼리 생성 실패, 기존 팔로우업 처리로 전환")
                answer, related_products = self._generate_followup_answer_with_llm(user_input, recent_qa_data)
                return FollowUpAgentResult(
                    success=True,
                    message=answer,
                    products=related_products,
                    metadata={"agent_type": "followup", "fallback": True}
                )
            
            # 검색 에이전트 실행 - LLM이 생성한 쿼리로 직접 검색
            search_result = search_agent.process_search_request(
                user_input=search_query,
                available_products=available_products,
                context_info=None,
                db=None,
                user_id=None
            )
            
            if search_result.success and search_result.products:
                # 챗봇 카드 호환성을 위해 필드 매핑
                for product in search_result.products:
                    # 가격 필드 매핑 (챗봇 JavaScript에서 '가격' 필드를 사용)
                    if '원가' in product and '가격' not in product:
                        product['가격'] = product['원가']
                    
                    # 이미지 URL 필드 매핑 (여러 필드명 지원)
                    image_url = product.get('사진') or product.get('이미지URL') or product.get('대표이미지URL') or ''
                    if image_url:
                        product['사진'] = image_url
                        product['이미지URL'] = image_url
                        product['대표이미지URL'] = image_url
                    
                    # 챗봇 JavaScript 호환성을 위한 추가 필드 매핑
                    if '상품코드' in product and 'product_id' not in product:
                        product['product_id'] = product['상품코드']
                    if '상품링크' in product and 'product_link' not in product:
                        product['product_link'] = product['상품링크']
                    if '상품명' in product and 'product_name' not in product:
                        product['product_name'] = product['상품명']
                    if '한글브랜드명' in product and 'brand_name' not in product:
                        product['brand_name'] = product['한글브랜드명']
                
                # LLM이 검색 결과에 대한 설명 생성
                explanation = self._generate_search_explanation(user_input, search_query, search_result.products)
                
                return FollowUpAgentResult(
                    success=True,
                    message=explanation,
                    products=search_result.products,
                    metadata={
                        "llm_guided_search": True, 
                        "agent_type": "followup_to_search",
                        "search_query": search_query,
                        "products_count": len(search_result.products)
                    }
                )
            else:
                return FollowUpAgentResult(
                    success=False,
                    message=f"'{search_query}' 관련 상품을 찾을 수 없습니다.",
                    products=[],
                    metadata={"llm_guided_search": True, "agent_type": "followup_to_search", "no_results": True}
                )
                
        except Exception as e:
            print(f"LLM 가이드 검색 오류: {e}")
            return FollowUpAgentResult(
                success=False,
                message="검색 중 오류가 발생했습니다.",
                products=[],
                metadata={"error": str(e), "agent_type": "followup_to_search"}
            )
    
    def _generate_search_query_with_llm(self, user_input: str, recent_qa_data: List[Dict]) -> str:
        """LLM이 사용자 질문을 바탕으로 적절한 검색 쿼리를 생성합니다."""
        try:
            # 최근 상품 정보 준비
            recent_products_info = ""
            recent_color = ""
            recent_category = ""
            
            if recent_qa_data and recent_qa_data[0].get('products_data'):
                products = recent_qa_data[0]['products_data'][:2]  # 최대 2개만
                recent_products_info = "최근 추천된 상품들:\n"
                for i, product in enumerate(products, 1):
                    name = product.get('상품명', '상품명 없음')
                    brand = product.get('한글브랜드명', '브랜드 없음')
                    category = product.get('대분류', '')
                    color = product.get('색상', '')
                    recent_products_info += f"{i}. {name} ({brand}) - {category} {color}\n"
                    
                    # 첫 번째 상품의 색상과 카테고리 저장
                    if i == 1:
                        recent_color = color
                        recent_category = category
            
            # 색상 조합 매핑 추가
            color_combination_hint = ""
            if recent_color and recent_category:
                color_combination_hint = f"""
**현재 상품 정보:**
- 색상: {recent_color}
- 카테고리: {recent_category}

**색상 조합 가이드:**
- 파란색 상의 → 검은색/흰색/베이지/카키 바지
- 빨간색 상의 → 검은색/흰색/베이지/네이비 바지  
- 흰색 상의 → 검은색/네이비/베이지/카키 바지
- 검은색 상의 → 흰색/베이지/네이비/카키 바지
- 베이지 상의 → 검은색/흰색/네이비/카키 바지
- 네이비 상의 → 흰색/베이지/검은색/카키 바지
"""



            prompt = f"""사용자의 질문을 바탕으로 상품 검색에 적합한 쿼리를 생성해주세요.

사용자 질문: {user_input}

{recent_products_info}
{color_combination_hint}

**카탈로그 (실제 데이터에 있는 카테고리만 사용):**
- 상의: 후드티, 셔츠/블라우스, 긴소매, 반소매, 피케/카라, 니트/스웨터, 슬리브리스
- 바지: 데님팬츠, 트레이닝/조거팬츠, 코튼팬츠, 슈트팬츠/슬랙스, 숏팬츠, 카고팬츠
- 스커트: 미니스커트, 미디스커트, 롱스커트
- 원피스: 맥시원피스, 미니원피스, 미디원피스

검색 쿼리 생성 규칙:
1. 이전 추천 상품과 조화로운 색상의 다른 카테고리 상품 검색
2. 같은 색상보다는 조화로운 색상 조합 우선
3. **하나의 구체적인 색상과 카테고리로 생성** (예: "검은색 데님팬츠", "흰색 슬랙스")
4. **중요**: "A에 어울리는 B" 형태로 생성하지 말고, 단순히 "B"만 생성하세요!
5. **카탈로그 준수**: 위에 명시된 카탈로그의 카테고리만 사용하세요!

검색 쿼리:"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50
            )
            
            query = response.choices[0].message.content.strip()
            print(f"🔍 LLM 생성 검색 쿼리: {query}")
            return query
            
        except Exception as e:
            print(f"검색 쿼리 생성 오류: {e}")
            return None
    
    def _generate_search_explanation(self, user_input: str, search_query: str, products: List[Dict]) -> str:
        """검색 결과에 대한 설명을 생성합니다."""
        try:
<<<<<<< Updated upstream
            prompt = f"""사용자의 질문과 검색 결과를 바탕으로 친근한 설명을 생성해주세요.

사용자 질문: {user_input}
검색 쿼리: {search_query}
검색된 상품 수: {len(products)}개

검색된 상품들:
{chr(10).join([f"- {p.get('상품명', '상품명 없음')} ({p.get('한글브랜드명', '브랜드 없음')}) - {p.get('원가', 0):,}원" for p in products[:3]])}

설명 스타일:
- 친근하고 도움이 되는 톤
- 사용자의 질문 의도를 반영
- 검색된 상품의 특징 간단히 언급
- 100자 이내로 간결하게

설명:"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100
            )
            
            explanation = response.choices[0].message.content.strip()
            return explanation
            
        except Exception as e:
            print(f"검색 설명 생성 오류: {e}")
            return f"'{search_query}' 관련 상품들을 찾았습니다!"
=======
            return f"'{search_query}'를 추천해드릴게요"
            
        except Exception as e:
            print(f"검색 설명 생성 오류: {e}")
            return f"'{search_query}'를 추천해드릴게요"
>>>>>>> Stashed changes

    def _check_recent_recommendations(self, db, user_id: int) -> bool:
        """최근 추천이 있는지 확인 (간소화 버전)"""
        try:
            recent_qa_data = self._get_recent_qa_data(db, user_id)
            return len(recent_qa_data) > 0
            
        except Exception as e:
            print(f"최근 추천 확인 오류: {e}")
            return False
