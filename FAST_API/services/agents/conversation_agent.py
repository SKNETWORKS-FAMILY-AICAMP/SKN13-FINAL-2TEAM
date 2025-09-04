"""
Conversation Intent Agent
상황별 대화형 추천을 처리하는 에이전트
"""
import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv
import random

from services.common_search import CommonSearchModule, SearchQuery, SearchResult


load_dotenv()

@dataclass
class ConversationAgentResult:
    """Conversation Agent 결과"""
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

class ConversationAgent:
    """대화형 추천 에이전트"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
        self.search_module = CommonSearchModule()
    
    def process_conversation_request(self, user_input: str, extracted_info: Dict,
                                   available_products: List[Dict],
                                   context_summaries: Optional[List[str]] = None) -> ConversationAgentResult:
        """
        대화형 추천 요청 처리
        
        Args:
            user_input: 사용자 입력
            extracted_info: 추출된 정보 (상황, 스타일 등)
            available_products: 추천할 상품 목록
            context_summaries: 이전 대화 요약들
        
        Returns:
            ConversationAgentResult: 추천 결과
        """
        print(f"=== Conversation Agent 시작 ===")
        print(f"사용자 입력: {user_input}")
        print(f"추출된 정보: {extracted_info}")
        print(f"컨텍스트 요약: {context_summaries}")
        
        try:
            # extracted_info가 비어있으면 내부 분석 수행
            if not extracted_info:
                extracted_info = self._analyze_conversation_request(user_input)
            
            # 1. 날씨 관련 요청인지 확인
            weather_context = self._check_weather_context(user_input)
            
            # 2. LLM으로 상황별 추천 스펙 생성
            recommendation_spec = self._generate_recommendation_spec(user_input, extracted_info, context_summaries, weather_context)
            
            if not recommendation_spec:
                return self._fallback_recommendation(user_input, available_products)
            
            # 2. 추천 스펙을 검색 쿼리로 변환
            search_queries = self._convert_spec_to_queries(recommendation_spec)
            
            # 3. 각 쿼리별로 상품 검색
            all_matched_products = []
            for query in search_queries:
                search_result = self.search_module.search_products(query, available_products)
                all_matched_products.extend(search_result.products)
            
            # 4. 상의/하의 균형 맞추기
            balanced_products = self._balance_products(all_matched_products)
            
            # 5. 최종 메시지 생성
            final_message = self._generate_final_message(
                user_input, recommendation_spec, balanced_products, context_summaries
            )
            

            
            return ConversationAgentResult(
                success=len(balanced_products) > 0,
                message=final_message,
                products=balanced_products,
                metadata={
                    "recommendation_spec": recommendation_spec,
                    "queries_used": len(search_queries),
                    "total_found": len(all_matched_products),
                    "agent_type": "conversation"
                }
            )
            
        except Exception as e:
            print(f"Conversation Agent 오류: {e}")
            return ConversationAgentResult(
                success=False,
                message="추천 생성 중 오류가 발생했습니다. 다시 시도해주세요.",
                products=[],
                metadata={"error": str(e), "agent_type": "conversation"}
            )
    
    def _check_weather_context(self, user_input: str) -> Optional[str]:
        """날씨 관련 요청인지 확인하고 날씨 정보 제공"""
        weather_keywords = ["날씨", "weather", "기온", "온도", "현재", "오늘"]
        
        if any(keyword in user_input.lower() for keyword in weather_keywords):
            # 간단한 날씨 설명 반환 (실제로는 WeatherAgent 호출할 수도 있음)
            return "현재 기온 15도, 선선한 가을 날씨"
        return None
    
    def _generate_recommendation_spec(self, user_input: str, extracted_info: Dict, 
                                    context_summaries: Optional[List[str]] = None,
                                    weather_context: Optional[str] = None) -> Optional[Dict]:
        """LLM으로 상황별 추천 스펙 생성"""
        
        # 컨텍스트 정보 구성
        context_str = ""
        if context_summaries:
            context_str = f"이전 대화 요약: {' | '.join(context_summaries[-3:])}"
        
        # 날씨 정보 추가
        weather_str = ""
        if weather_context:
            weather_str = f"현재 날씨 정보: {weather_context}"
        
        system_prompt = f"""당신은 의류 스타일링 전문가입니다.
사용자의 상황과 요청에 맞는 구체적인 의상 스펙을 제안해주세요.

사용자 요청 분석:
- 상황: {extracted_info.get('situations', [])}
- 스타일: {extracted_info.get('styles', [])}
- 색상: {extracted_info.get('colors', [])}
- 브랜드: {extracted_info.get('brands', [])}

{context_str}
{weather_str}

다음 JSON 형식으로 응답해주세요:
{{
    "recommendations": [
        {{
            "category": "상의|하의",
            "color": "구체적인 색상",
            "type": "구체적인 의류 종류",
            "reason": "추천 이유",
            "brands": "추출된 브랜드들",
        }}
    ],
    "styling_tips": "전체적인 스타일링 팁",
    "occasion_analysis": "상황 분석 및 적합성"
}}

규칙:
1. 상의 2개, 하의 2개 추천
2. 색상 조합이 조화롭게
3. 상황에 맞는 스타일
4. 의류 종류는 다음 중에서만 사용:
   - 상의: 후드티, 셔츠/블라우스, 긴소매, 반소매, 피케/카라, 니트/스웨터, 슬리브리스
   - 하의: 데님팬츠, 트레이닝/조거팬츠, 코튼팬츠, 슈트팬츠/슬랙스, 숏팬츠, 카고팬츠 
   - 스커트 : 미니스커트, 미디스커트, 롱스커트
   - 원피스 : 미니원피스, 미디원피스, 맥시원피스
5. 색상은 기본 색상명 사용 (블랙, 화이트, 그레이, 네이비, 베이지, 브라운, 카키 등)
6. 이전 대화 내용이 있으면 연관성 고려"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"사용자 요청: {user_input}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            print(f"생성된 추천 스펙: {result}")
            return result
            
        except Exception as e:
            print(f"추천 스펙 생성 오류: {e}")
            return None
    
    def _convert_spec_to_queries(self, recommendation_spec: Dict) -> List[SearchQuery]:
        """추천 스펙을 검색 쿼리들로 변환"""
        queries = []
        
        for rec in recommendation_spec.get("recommendations", []):
            category = rec.get("category", "")
            color = rec.get("color", "")
            item_type = rec.get("type", "")
            
            # 필수 정보가 있는 경우만 쿼리 생성
            if category and color and item_type:
                # 브랜드 정보 추출
                brands = []
                if rec.get("brands"):
                    if isinstance(rec["brands"], str):
                        brands = [rec["brands"]]
                    elif isinstance(rec["brands"], list):
                        brands = rec["brands"]
                
                query = SearchQuery(
                    colors=[color],
                    categories=[item_type],  # 원본 타입 그대로 사용
                    situations=[],
                    styles=[],
                    brands=brands
                )
                queries.append(query)
        
        return queries
    
    def _balance_products(self, products: List[Dict]) -> List[Dict]:
        """상의/하의 균형을 맞춰 최종 상품 선택"""
        if not products:
            return []
        
        # 상의/하의 분류
        top_products = []
        bottom_products = []
        
        for product in products:
            대분류 = product.get("대분류", "").lower()
            소분류 = product.get("소분류", "").lower()
            
            if any(keyword in 대분류 or keyword in 소분류 
                  for keyword in ["상의", "탑", "top", "셔츠", "니트", "후드"]):
                top_products.append(product)
            elif any(keyword in 대분류 or keyword in 소분류 
                    for keyword in ["하의", "바텀", "bottom", "바지", "팬츠", "pants"]):
                bottom_products.append(product)
        
        # 균형 맞춰 선택
        final_products = []
        
        if len(top_products) >= 2 and len(bottom_products) >= 2:
            final_products.extend(random.sample(top_products, 2))
            final_products.extend(random.sample(bottom_products, 2))
        elif len(top_products) >= 2:
            final_products.extend(random.sample(top_products, 2))
            remaining = min(2, len(bottom_products))
            if remaining > 0:
                final_products.extend(random.sample(bottom_products, remaining))
        elif len(bottom_products) >= 2:
            final_products.extend(random.sample(bottom_products, 2))
            remaining = min(2, len(top_products))
            if remaining > 0:
                final_products.extend(random.sample(top_products, remaining))
        else:
            # 균형이 안 맞으면 전체에서 4개 선택
            count = min(4, len(products))
            final_products = random.sample(products, count)
        
        # 중복 제거
        seen_ids = set()
        unique_products = []
        for product in final_products:
            product_id = product.get("상품코드", id(product))
            if product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_products.append(product)
        
        return unique_products[:4]
    
    def _generate_final_message(self, user_input: str, recommendation_spec: Dict,
                              products: List[Dict], context_summaries: Optional[List[str]]) -> str:
        """최종 추천 메시지 생성"""
        if not products:
            return f"'{user_input}'에 맞는 상품을 찾지 못했습니다. 다른 조건으로 검색해보세요."
        
        message = f"'{user_input}'에 맞는 스타일을 추천해드릴게요! ✨\n\n"
        
        # 상황 분석 추가
        if recommendation_spec.get("occasion_analysis"):
            message += f"**상황 분석**: {recommendation_spec['occasion_analysis']}\n\n"
        
        # 상의/하의 분류하여 표시
        top_products = []
        bottom_products = []
        
        for product in products:
            대분류 = product.get("대분류", "").lower()
            if any(keyword in 대분류 for keyword in ["상의", "탑", "top"]):
                top_products.append(product)
            else:
                bottom_products.append(product)
        
        # 상의 섹션
        if top_products:
            message += "👕 **상의 추천**\n"
            for i, product in enumerate(top_products, 1):
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                price = product.get('원가', 0)
                
                message += f"**{i}. {product_name}**\n"
                message += f"   📍 브랜드: {brand}\n"
                if price:
                    message += f"   💰 가격: {price:,}원\n"
                message += "\n"
        
        # 하의 섹션
        if bottom_products:
            message += "👖 **하의 추천**\n"
            for i, product in enumerate(bottom_products, 1):
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                price = product.get('원가', 0)
                
                message += f"**{i}. {product_name}**\n"
                message += f"   📍 브랜드: {brand}\n"
                if price:
                    message += f"   💰 가격: {price:,}원\n"
                message += "\n"
        
        # 스타일링 팁 추가
        if recommendation_spec.get("styling_tips"):
            message += f"💡 **스타일링 팁**\n{recommendation_spec['styling_tips']}"
        
        return message
    
    def _fallback_recommendation(self, user_input: str, available_products: List[Dict]) -> ConversationAgentResult:
        """LLM 추천이 실패했을 때 기본 추천"""
        if len(available_products) >= 4:
            selected_products = random.sample(available_products, 4)
        else:
            selected_products = available_products
        
        message = f"'{user_input}'에 대한 추천 상품입니다! 🛍️\n\n"
        
        for i, product in enumerate(selected_products, 1):
            product_name = product.get('상품명', '상품명 없음')
            brand = product.get('한글브랜드명', '브랜드 없음')
            price = product.get('원가', 0)
            
            message += f"**{i}. {product_name}**\n"
            message += f"   📍 브랜드: {brand}\n"
            if price:
                message += f"   💰 가격: {price:,}원\n"
            message += "\n"
        
        return ConversationAgentResult(
            success=len(selected_products) > 0,
            message=message,
            products=selected_products,
            metadata={"fallback": True, "agent_type": "conversation"}
        )
    

    
    def _analyze_conversation_request(self, user_input: str) -> Dict:
        """사용자 입력을 분석하여 대화형 추천 정보 추출 (내부 LLM 분석)"""
        system_prompt = """당신은 대화형 의류 추천 시스템의 분석기입니다.
사용자의 입력을 분석하여 다음 정보를 추출해주세요.

**응답 형식 (JSON):**
{
    "situations": ["추출된 상황들"],
    "styles": ["추출된 스타일들"],
    "colors": ["추출된 색상들"],
    "categories": ["추출된 카테고리들"]
}

**중요 규칙:**
1. 상황: 데이트, 출근, 하객, 야외활동, 운동, 여행, 파티, 면접, 캐주얼 등
2. 스타일: 캐주얼, 정장, 스포티, 빈티지, 미니멀, 우아한, 섹시한 등
3. 색상: 빨간색, 파란색, 검은색, 흰색, 베이지, 네이비, 카키, 민트, 와인, 올리브 등
4. 카테고리: 후드티, 셔츠, 청바지, 원피스, 스커트 등"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"사용자 입력: {user_input}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"대화형 추천 요청 분석 오류: {e}")
            # 오류 시 기본값 반환
            return {"situations": [], "styles": [], "colors": [], "categories": []}