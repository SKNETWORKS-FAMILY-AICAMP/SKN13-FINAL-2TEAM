import os
import json
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

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

@dataclass
class ToolResult:
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

@dataclass
class LLMResponse:
    intent_result: IntentResult
    tool_result: Optional[ToolResult]
    final_message: str
    products: List[Dict]

class LLMService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-3.5-turbo"
        
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
                intent="general",
                confidence=0.5,
                extracted_info={"keywords": [user_input]},
                original_query=user_input
            )
    
    def search_products(self, intent_result: IntentResult, available_products: List[Dict]) -> ToolResult:
        """검색 기반 상품 추천을 수행합니다."""
        
        # 기존 필터링 로직 활용
        from routers.router_chatbot import exact_match_filter

        # 정확 매칭 필터링 적용
        filtered_products = exact_match_filter(intent_result.original_query, available_products)
        
        if filtered_products:
            message = f"'{intent_result.original_query}'에 맞는 상품을 찾았습니다! 🔍\n\n추천 상품:\n"
            
            # 상품 정보를 메시지에 추가
            for i, product in enumerate(filtered_products[:4], 1):  # 최대 4개만
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                price = product.get('할인가', 0)
                
                message += f"{i}. {product_name}, {brand}"
                if price:
                    message += f", {price:,}원"
                message += "\n"
        else:
            message = f"'{intent_result.original_query}'에 맞는 상품을 찾지 못했습니다. 다른 키워드로 검색해보세요."
        
        return ToolResult(
            success=len(filtered_products) > 0,
            message=message,
            products=filtered_products,
            metadata={"filter_type": "exact_match"}
        )
    
    def conversation_recommendation(self, intent_result: IntentResult, available_products: List[Dict]) -> ToolResult:
        """대화 기반 상황별 추천을 수행합니다."""
        
        system_prompt = """당신은 의류 스타일링 전문가입니다.
사용자의 상황과 요청에 맞는 구체적인 의상 스펙을 제안해주세요.

사용자 요청 분석:
- 상황: {situations}
- 스타일: {styles}
- 키워드: {keywords}

다음 JSON 형식으로 응답해주세요:
{{
    "message": "상황별 추천 메시지",
    "recommendations": [
        {{
            "category": "상의 또는 하의",
            "color": "색상",
            "type": "의류종류 (셔츠, 티셔츠, 슬랙스, 청바지 등)",
            "reason": "추천 이유"
        }},
        {{
            "category": "상의 또는 하의", 
            "color": "색상",
            "type": "의류종류",
            "reason": "추천 이유"
        }}
    ],
    "styling_tips": "전체적인 스타일링 팁"
}}

중요: 
- 상의 2개 + 하의 2개를 균형있게 제안해주세요
- 각 의상의 색상과 종류를 구체적으로 명시해주세요
- 상황에 맞는 실용적인 조합을 제안해주세요"""

        messages = [
            {"role": "system", "content": system_prompt.format(
                situations=", ".join(intent_result.extracted_info.get("situations", [])),
                styles=", ".join(intent_result.extracted_info.get("styles", [])),
                keywords=", ".join(intent_result.extracted_info.get("keywords", []))
            )},
            {"role": "user", "content": intent_result.original_query}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=800
            )
            
            result_text = response.choices[0].message.content
            print(f"LLM 원본 응답: {result_text}")
            
            try:
                result = json.loads(result_text)
                print(f"LLM 파싱된 결과: {result}")
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류: {e}")
                print(f"파싱 실패한 텍스트: {result_text}")
                # JSON 파싱 실패 시 기본 응답 생성
                result = {
                    "message": f"'{intent_result.original_query}'에 대한 상황별 추천을 제공합니다! 💡",
                    "recommendations": [],
                    "styling_tips": "상황에 맞는 의상을 선택해보세요."
                }
            
            # LLM이 제안한 스펙으로 상품 검색
            selected_products = []
            recommendation_text = result["message"] + "\n\n추천 의상:\n"
            
            for i, rec in enumerate(result.get("recommendations", []), 1):
                category = rec.get("category", "")
                color = rec.get("color", "")
                item_type = rec.get("type", "")
                reason = rec.get("reason", "")
                
                print(f"추천 {i}: {category}, {color}, {item_type}, {reason}")
                
                # 검색 쿼리 생성 (더 유연하게)
                search_queries = []
                
                # 1. 원본 쿼리
                search_queries.append(f"{color} {item_type}")
                
                # 2. 카테고리별 대체 쿼리
                if category == "상의":
                    if "블라우스" in item_type:
                        search_queries.extend([f"{color} 셔츠", f"{color} 블라우스", f"{color} 상의"])
                    elif "카디건" in item_type:
                        search_queries.extend([f"{color} 니트", f"{color} 상의", f"{color} 티셔츠"])
                    else:
                        search_queries.extend([f"{color} 상의", f"{color} 셔츠", f"{color} 티셔츠"])
                elif category == "하의":
                    if "슬랙스" in item_type:
                        search_queries.extend([f"{color} 슬랙스", f"{color} 팬츠", f"{color} 바지"])
                    elif "스커트" in item_type:
                        search_queries.extend([f"{color} 스커트", f"{color} 치마", f"{color} 하의"])
                    else:
                        search_queries.extend([f"{color} 하의", f"{color} 팬츠", f"{color} 바지"])
                
                # 3. 색상만으로 검색
                search_queries.append(color)
                
                print(f"검색 쿼리들: {search_queries}")
                
                # 여러 쿼리로 검색 시도
                best_match = None
                used_query = ""
                
                for query in search_queries:
                    from routers.router_chatbot import exact_match_filter
                    filtered_products = exact_match_filter(query, available_products)
                    
                    print(f"검색 쿼리: '{query}', 결과: {len(filtered_products)}개")
                    
                    if filtered_products:
                        # 카테고리와 일치하는 상품 우선 선택
                        for product in filtered_products:
                            product_category = str(product.get('대분류', '')).strip()
                            if ((category == "상의" and product_category == "상의") or 
                                (category == "하의" and product_category in ["하의", "바지"])):
                                best_match = product
                                used_query = query
                                break
                        
                        # 카테고리 일치하는 상품이 없으면 첫 번째 상품 선택
                        if not best_match:
                            best_match = filtered_products[0]
                            used_query = query
                        break
                
                # 가장 적합한 상품 선택
                if best_match:
                    selected_products.append(best_match)
                    
                    # 추천 텍스트에 상품 정보 추가 (실제 찾은 상품만)
                    product_name = best_match.get('상품명', '상품명 없음')
                    brand = best_match.get('한글브랜드명', '브랜드 없음')
                    price = best_match.get('할인가', 0)
                    
                    recommendation_text += f"{i}. {color} {item_type} - {product_name}, {brand}"
                    if price:
                        recommendation_text += f", {price:,}원"
                    recommendation_text += f"\n   추천 이유: {reason}\n"
                # else:
                    # 매칭되는 상품이 없으면 텍스트에 추가하지 않음 (제거됨)
                    # recommendation_text += f"{i}. {color} {item_type}\n   추천 이유: {reason}\n"
            
            # 스타일링 팁 추가
            if result.get("styling_tips"):
                recommendation_text += f"\n💡 스타일링 팁: {result['styling_tips']}"
            
            # 상의/하의 균형 맞추기 (더 엄격하게)
            balanced_products = self._balance_top_bottom_products_strict(selected_products, available_products)
            
            print(f"최종 선택된 상품 수: {len(balanced_products)}")
            
            return ToolResult(
                success=True,
                message=recommendation_text,
                products=balanced_products,
                metadata={
                    "styling_tips": result.get("styling_tips", ""),
                    "recommendations": result.get("recommendations", [])
                }
            )
            
        except Exception as e:
            print(f"대화 기반 추천 오류: {e}")
            # 오류 시 기본 필터링 사용
            from routers.router_chatbot import situation_filter
            
            # 상황 추출
            situations = intent_result.extracted_info.get("situations", [])
            situation = situations[0] if situations else "일반"
            
            filtered_products = situation_filter(situation, available_products)
            
            # 메시지는 간단하게만 표시
            message = f"'{intent_result.original_query}'에 대한 상황별 추천을 제공합니다! 💡"
            
            return ToolResult(
                success=len(filtered_products) > 0,
                message=message,
                products=filtered_products,
                metadata={"fallback": "situation_filter"}
            )
    
    def _balance_top_bottom_products(self, selected_products: List[Dict], available_products: List[Dict]) -> List[Dict]:
        """상의/하의 균형을 맞춰서 상품을 선택합니다."""
        
        # 상의/하의 분류
        top_products = []
        bottom_products = []
        
        for product in selected_products:
            product_text = f"{product.get('상품명', '')} {product.get('영어브랜드명', '')} {product.get('대분류', '')} {product.get('소분류', '')}".lower()
            대분류 = str(product.get('대분류', '')).strip()
            소분류 = str(product.get('소분류', '')).strip()
            
            # 상의/하의 판별
            is_top = (대분류 in ["상의", "탑", "TOP", "상의류"] or 
                     소분류 in ["상의", "탑", "TOP", "상의류"] or
                     any(keyword in product_text for keyword in ["티셔츠", "tshirt", "t-shirt", "셔츠", "shirt", "니트", "knit", "후드", "hood", "맨투맨", "sweat"]))
            
            is_bottom = (대분류 in ["하의", "바텀", "BOTTOM", "하의류", "팬츠", "반바지", "숏팬츠", "쇼츠", "SHORTS", "바지"] or
                        소분류 in ["하의", "바텀", "BOTTOM", "하의류", "팬츠", "반바지", "숏팬츠", "쇼츠", "SHORTS", "바지"] or
                        any(keyword in product_text for keyword in ["숏팬츠", "반바지", "쇼츠", "shorts", "팬츠", "pants", "바지", "슬랙스", "청바지", "데님", "jeans"]))
            
            if is_top and not is_bottom:
                top_products.append(product)
            elif is_bottom and not is_top:
                bottom_products.append(product)
        
        # 상의 2개 + 하의 2개로 균형 맞추기
        result = []
        
        # 상의 2개 선택
        if len(top_products) >= 2:
            result.extend(random.sample(top_products, 2))
        elif top_products:
            result.extend(top_products)
        
        # 하의 2개 선택
        if len(bottom_products) >= 2:
            result.extend(random.sample(bottom_products, 2))
        elif bottom_products:
            result.extend(bottom_products)
        
        # 부족한 경우 전체 상품에서 추가
        if len(result) < 4:
            remaining_products = [p for p in available_products if p not in result]
            if remaining_products:
                additional_count = min(4 - len(result), len(remaining_products))
                result.extend(random.sample(remaining_products, additional_count))
        
        return result[:4]

    def _balance_top_bottom_products_strict(self, selected_products: List[Dict], available_products: List[Dict]) -> List[Dict]:
        """상의/하의 균형을 엄격하게 2개씩 맞추어 선택합니다."""
        
        # 상의/하의 분류
        top_products = []
        bottom_products = []
        
        for product in selected_products:
            product_text = f"{product.get('상품명', '')} {product.get('영어브랜드명', '')} {product.get('대분류', '')} {product.get('소분류', '')}".lower()
            대분류 = str(product.get('대분류', '')).strip()
            소분류 = str(product.get('소분류', '')).strip()
            
            # 상의/하의 판별 (새로운 소분류 기준)
            is_top = (대분류 in ["상의"] or 
                     소분류 in ["후드티", "셔츠블라우스", "긴소매", "반소매", "피케카라", "니트스웨터", "슬리브리스", "애슬레저"] or
                     any(keyword in product_text for keyword in ["티셔츠", "tshirt", "t-shirt", "셔츠", "shirt", "니트", "knit", "후드", "hood", "맨투맨", "sweat", "블라우스", "blouse"]))
            
            is_bottom = (대분류 in ["하의", "바지"] or
                        소분류 in ["데님 팬츠", "트레이닝/조거 팬츠", "코튼 팬츠", "슈트 팬츠/슬랙스", "숏 팬츠", "레깅스"] or
                        any(keyword in product_text for keyword in ["숏팬츠", "반바지", "쇼츠", "shorts", "팬츠", "pants", "바지", "슬랙스", "청바지", "데님", "jeans", "조거", "jogger", "트레이닝", "training", "레깅스", "leggings"]))
            
            if is_top and not is_bottom:
                top_products.append(product)
            elif is_bottom and not is_top:
                bottom_products.append(product)
        
        print(f"분류 결과 - 상의: {len(top_products)}개, 하의: {len(bottom_products)}개")
        
        result = []
        
        # 상의 정확히 2개 선택
        if len(top_products) >= 2:
            result.extend(random.sample(top_products, 2))
        elif top_products:
            result.extend(top_products)
            # 부족한 상의는 전체 상품에서 상의 찾아서 추가
            remaining_tops = [p for p in available_products if p not in result and 
                            (str(p.get('대분류', '')).strip() in ["상의"] or
                             str(p.get('소분류', '')).strip() in ["후드티", "셔츠블라우스", "긴소매", "반소매", "피케카라", "니트스웨터", "슬리브리스", "애슬레저"] or
                             any(keyword in f"{p.get('상품명', '')} {p.get('영어브랜드명', '')}".lower() 
                                 for keyword in ["티셔츠", "tshirt", "t-shirt", "셔츠", "shirt", "니트", "knit", "후드", "hood", "맨투맨", "sweat", "블라우스", "blouse"]))]
            if remaining_tops:
                needed_tops = 2 - len(top_products)
                result.extend(random.sample(remaining_tops, min(needed_tops, len(remaining_tops))))
        
        # 하의 정확히 2개 선택
        if len(bottom_products) >= 2:
            result.extend(random.sample(bottom_products, 2))
        elif bottom_products:
            result.extend(bottom_products)
            # 부족한 하의는 전체 상품에서 하의 찾아서 추가
            remaining_bottoms = [p for p in available_products if p not in result and 
                               (str(p.get('대분류', '')).strip() in ["하의", "바지"] or
                                str(p.get('소분류', '')).strip() in ["데님 팬츠", "트레이닝/조거 팬츠", "코튼 팬츠", "슈트 팬츠/슬랙스", "숏 팬츠", "레깅스"] or
                                any(keyword in f"{p.get('상품명', '')} {p.get('영어브랜드명', '')}".lower() 
                                    for keyword in ["숏팬츠", "반바지", "쇼츠", "shorts", "팬츠", "pants", "바지", "슬랙스", "청바지", "데님", "jeans", "조거", "jogger", "트레이닝", "training", "레깅스", "leggings"]))]
            if remaining_bottoms:
                needed_bottoms = 2 - len(bottom_products)
                result.extend(random.sample(remaining_bottoms, min(needed_bottoms, len(remaining_bottoms))))
        
        # 최종적으로 정확히 4개만 반환 (상의 2개 + 하의 2개)
        final_result = result[:4]
        
        # 최종 분류 확인
        final_tops = 0
        final_bottoms = 0
        for product in final_result:
            대분류 = str(product.get('대분류', '')).strip()
            if 대분류 in ["상의"]:
                final_tops += 1
            elif 대분류 in ["하의", "바지"]:
                final_bottoms += 1
        
        print(f"최종 결과 - 상의: {final_tops}개, 하의: {final_bottoms}개")
        
        return final_result
    
    def _build_context(self, chat_history: List[ChatMessage]) -> str:
        """대화 컨텍스트를 구성합니다."""
        if not chat_history:
            return "대화 기록이 없습니다."
        
        # 최근 3쌍의 대화만 사용
        recent_history = chat_history[-6:]  # 3쌍 = 6개 메시지
        
        context_lines = []
        for msg in recent_history:
            role = "사용자" if msg.role == "user" else "챗봇"
            context_lines.append(f"{role}: {msg.content}")
        
        return "\n".join(context_lines)

    def analyze_intent_and_call_tool(self, user_input: str, conversation_context: str = "", available_products: List[Dict] = None) -> LLMResponse:
        """의도 분석과 툴 호출을 통합하여 처리합니다."""
        
        # 대화 컨텍스트를 ChatMessage 형태로 변환
        chat_history = self._parse_context_to_messages(conversation_context)
        
        # 1단계: 의도 분류
        intent_result = self.classify_intent(user_input, chat_history)
        print(f"의도 분류 결과: {intent_result.intent} (신뢰도: {intent_result.confidence})")
        
        # 2단계: 의도에 따른 툴 호출
        tool_result = None
        final_message = ""
        products = []
        
        if intent_result.intent == "search":
            if available_products:
                tool_result = self.search_products(intent_result, available_products)
                final_message = tool_result.message
                products = tool_result.products
            else:
                final_message = f"'{user_input}'에 대한 검색을 수행하겠습니다! 🔍"
                
        elif intent_result.intent == "conversation":
            if available_products:
                tool_result = self.conversation_recommendation(intent_result, available_products)
                final_message = tool_result.message
                products = tool_result.products
            else:
                final_message = f"'{user_input}'에 대한 상황별 추천을 제공하겠습니다! 💡"
                
        else:  # general
            final_message = self._generate_general_response(user_input, intent_result)
        
        return LLMResponse(
            intent_result=intent_result,
            tool_result=tool_result,
            final_message=final_message,
            products=products
        )
    
    def _parse_context_to_messages(self, context: str) -> List[ChatMessage]:
        """대화 컨텍스트를 ChatMessage 리스트로 변환합니다."""
        if not context:
            return []
        
        messages = []
        lines = context.strip().split('\n')
        
        for line in lines:
            if line.startswith('사용자: '):
                content = line.replace('사용자: ', '').strip()
                messages.append(ChatMessage(role="user", content=content))
            elif line.startswith('챗봇: '):
                content = line.replace('챗봇: ', '').strip()
                messages.append(ChatMessage(role="assistant", content=content))
        
        return messages
    
    def _generate_general_response(self, user_input: str, intent_result: IntentResult) -> str:
        """일반적인 대화에 대한 응답을 생성합니다."""
        
        system_prompt = """당신은 친근하고 도움이 되는 의류 추천 챗봇입니다.
사용자의 일반적인 대화나 질문에 대해 친근하고 도움이 되는 응답을 해주세요.

응답은 다음 중 하나의 스타일로 해주세요:
1. 인사나 감사에 대한 친근한 응답
2. 도움말이나 사용법 안내
3. 의류 추천 서비스 소개
4. 기타 친근한 대화

한국어로 자연스럽고 친근하게 응답해주세요."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"일반 응답 생성 오류: {e}")
            return "안녕하세요! 의류 추천을 도와드릴게요. 어떤 스타일을 찾으시나요? 😊"
