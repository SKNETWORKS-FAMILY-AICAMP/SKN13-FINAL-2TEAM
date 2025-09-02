"""
Search Intent Agent
구체적인 상품 검색 요청을 처리하는 에이전트
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

from services.common_search import CommonSearchModule, SearchQuery, SearchResult


load_dotenv()

@dataclass
class SearchAgentResult:
    """Search Agent 결과"""
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

class SearchAgent:
    """검색 에이전트"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
        self.search_module = CommonSearchModule()
    
    def process_search_request(self, user_input: str, extracted_info: Dict, 
                             available_products: List[Dict], 
                             context_info: Optional[Dict] = None,
                             db=None, user_id: Optional[int] = None) -> SearchAgentResult:
        """
        검색 요청 처리
        
        Args:
            user_input: 사용자 입력
            extracted_info: 추출된 정보 (색상, 카테고리 등)
            available_products: 검색할 상품 목록
            context_info: 컨텍스트 정보 (이전 추천 등)
        
        Returns:
            SearchAgentResult: 검색 결과
        """
        print(f"=== Search Agent 시작 ===")
        print(f"사용자 입력: {user_input}")
        print(f"추출된 정보: {extracted_info}")
        
        try:
            # 1. 검색 쿼리 구성
            search_query = self._build_search_query(extracted_info, user_input)
            
            # 2. 컨텍스트 기반 필터 구성
            context_filters = self._build_context_filters(context_info) if context_info else None
            
            # 3. 상품 검색 실행
            search_result = self.search_module.search_products(
                query=search_query,
                available_products=available_products,
                context_filters=context_filters
            )
            
            # 4. 결과 메시지 생성
            if search_result.products:
                # LLM을 사용한 향상된 메시지 생성
                context_summaries = context_info.get("previous_summaries", []) if context_info else []
                message = self.enhance_search_with_llm(user_input, search_result, context_summaries, search_query)
                success = True
            else:
                message = f"'{user_input}' 조건에 맞는 상품을 찾지 못했습니다. 다른 조건으로 검색해보세요."
                success = False
            
            return SearchAgentResult(
                success=success,
                message=message,
                products=search_result.products,
                metadata={
                    "search_summary": search_result.search_summary,
                    "applied_filters": search_result.applied_filters,
                    "total_found": search_result.total_count,
                    "agent_type": "search"
                }
            )
            
        except Exception as e:
            print(f"Search Agent 오류: {e}")
            return SearchAgentResult(
                success=False,
                message="검색 중 오류가 발생했습니다. 다시 시도해주세요.",
                products=[],
                metadata={"error": str(e), "agent_type": "search"}
            )
    
    def _build_search_query(self, extracted_info: Dict, user_input: str) -> SearchQuery:
        """추출된 정보를 바탕으로 검색 쿼리 구성"""
        return SearchQuery(
            colors=extracted_info.get("colors", []),
            categories=extracted_info.get("categories", []),
            situations=extracted_info.get("situations", []),
            styles=extracted_info.get("styles", []),
            locations=extracted_info.get("locations", []),
            brands=extracted_info.get("brands", []),
            price_range=extracted_info.get("price_range")
        )
    
    def _build_context_filters(self, context_info: Dict) -> Dict:
        """컨텍스트 정보를 바탕으로 추가 필터 구성"""
        filters = {}
        
        # 이전 추천 상품이 있으면 브랜드 차별화
        if context_info.get("previous_products"):
            previous_brands = set()
            previous_prices = []
            
            for product in context_info["previous_products"]:
                brand = product.get("한글브랜드명")
                if brand:
                    previous_brands.add(brand)
                
                price = product.get("원가")
                if isinstance(price, (int, float)) and price > 0:
                    previous_prices.append(price)
            
            if previous_brands:
                filters["exclude_brands"] = list(previous_brands)
            
            if previous_prices:
                avg_price = sum(previous_prices) / len(previous_prices)
                filters["price_differentiation"] = avg_price
        
        # 스타일 다양화 요청
        if context_info.get("diversify_style"):
            filters["style_diversification"] = True
        
        return filters
    
    
    def enhance_search_with_llm(self, user_input: str, search_result: SearchResult, 
                               context_summaries: List[str], query: SearchQuery = None) -> str:
        """
        LLM을 사용하여 검색 결과를 향상시킨 메시지 생성
        """
        if not search_result.products:
            return search_result.search_summary
        
        # 컨텍스트 요약이 있으면 활용
        context_str = ""
        if context_summaries:
            context_str = f"\n이전 대화 요약: {' | '.join(context_summaries[-3:])}"
        
        # 실제 상품 정보를 프롬프트에 포함
        products_info = ""
        for i, product in enumerate(search_result.products, 1):
            product_name = product.get('상품명', '상품명 없음')
            brand = product.get('한글브랜드명', '브랜드 없음')
            price = product.get('원가', 0)
            
            products_info += f"\n{i}. 상품명: {product_name}\n   브랜드: {brand}\n   가격: {price:,}원\n"
        
        system_prompt = f"""당신은 친근하고 전문적인 의류 상담사입니다.
사용자의 검색 요청에 맞는 상품들을 구체적이고 유용하게 설명해주세요.

사용자 요청: {user_input}
검색 결과: {len(search_result.products)}개 상품 발견
적용된 필터: {search_result.applied_filters}
{context_str}

**실제 상품 정보:**
{products_info}

**응답 형식:**
1. **인사 및 요약** (1-2줄): "안녕하세요! [요청]에 맞는 [개수]개 상품을 찾았어요! 😊"
2. **추천 이유** (1줄): "이 상품들을 추천하는 이유는 [색상/스타일/상황]에 최적이기 때문이에요."
3. **상품별 설명** (상품당 2-3줄): 위의 실제 상품명과 브랜드를 사용하여 각 상품의 특징과 어울리는 상황을 구체적으로 설명
4. **스타일링 팁** (1-2줄): 전체적인 코디 조합이나 추가 아이템 제안

**중요 규칙:**
- 반드시 위에 제공된 실제 상품명과 브랜드를 그대로 사용하세요
- 가상의 상품명이나 브랜드를 만들어내지 마세요
- 각 상품의 설명은 해당 상품의 실제 정보를 바탕으로 작성하세요

**톤 가이드라인:**
- 친근하지만 전문적인 의류 상담사처럼 응답
- 이모지 적절히 사용 (상품별 📍, 가격 💰, 스타일 ✨)
- 간결하고 명확한 설명 (전체 8-12줄)
- 사용자가 실제로 구매할 수 있도록 도움이 되는 정보 제공"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"위 조건으로 {len(search_result.products)}개 상품을 찾았습니다. 자연스러운 추천 메시지를 작성해주세요."}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            enhanced_message = response.choices[0].message.content.strip()
            
            return enhanced_message
            
        except Exception as e:
            print(f"LLM 향상 메시지 생성 오류: {e}")
            # 오류 시 기본 메시지 반환
            return self.search_module.generate_search_message(search_result, SearchQuery())
