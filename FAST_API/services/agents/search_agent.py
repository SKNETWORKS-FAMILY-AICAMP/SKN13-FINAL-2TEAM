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
                message = self.enhance_search_with_llm(user_input, search_result, context_summaries)
                success = True
                
                # 5. recommendation 테이블에 저장
                if db and user_id and search_result.products:
                    self._save_search_recommendations(db, user_id, user_input, search_result.products)
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
            brands=extracted_info.get("brands", [])
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
    
    def _save_search_recommendations(self, db, user_id: int, query: str, products: List[Dict]):
        """검색 결과를 recommendation 테이블에 저장"""
        try:
            from crud.recommendation_crud import create_multiple_recommendations
            
            recommendations_data = []
            for product in products[:4]:  # 최대 4개만 저장
                item_id = product.get("상품코드", 0)
                if item_id:
                    recommendations_data.append({
                        "item_id": item_id,
                        "query": query,
                        "reason": f"검색 조건 '{query}'에 매칭된 상품"
                    })
            
            if recommendations_data:
                create_multiple_recommendations(db, user_id, recommendations_data)
                print(f"✅ 검색 결과 {len(recommendations_data)}개를 recommendation 테이블에 저장했습니다.")
            else:
                print("⚠️ 저장할 검색 결과가 없습니다.")
                
        except Exception as e:
            print(f"❌ 검색 결과 저장 중 오류: {e}")
            # 저장 실패해도 검색은 계속 진행
    
    def enhance_search_with_llm(self, user_input: str, search_result: SearchResult, 
                               context_summaries: List[str]) -> str:
        """
        LLM을 사용하여 검색 결과를 향상시킨 메시지 생성
        """
        if not search_result.products:
            return search_result.search_summary
        
        # 컨텍스트 요약이 있으면 활용
        context_str = ""
        if context_summaries:
            context_str = f"\n이전 대화 요약: {' | '.join(context_summaries[-3:])}"
        
        system_prompt = f"""당신은 의류 추천 전문가입니다.
사용자의 검색 요청에 대한 상품 추천 결과를 자연스럽고 친근한 톤으로 설명해주세요.

사용자 요청: {user_input}
검색 결과: {len(search_result.products)}개 상품 발견
적용된 필터: {search_result.applied_filters}
{context_str}

다음 형식으로 응답해주세요:
1. 친근한 인사 및 검색 결과 요약
2. 추천 이유 설명
3. 상품별 간단한 설명과 어울리는 상황
4. 추가 추천이나 스타일링 팁

톤: 친근하고 전문적, 이모지 적절히 사용"""

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
            
            # 상품 정보 추가
            enhanced_message += "\n\n📋 **추천 상품 목록**\n"
            for i, product in enumerate(search_result.products, 1):
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                price = product.get('원가', 0)
                
                enhanced_message += f"**{i}. {product_name}**\n"
                enhanced_message += f"   📍 브랜드: {brand}\n"
                if price:
                    enhanced_message += f"   💰 가격: {price:,}원\n"
                enhanced_message += "\n"
            
            return enhanced_message
            
        except Exception as e:
            print(f"LLM 향상 메시지 생성 오류: {e}")
            # 오류 시 기본 메시지 반환
            return self.search_module.generate_search_message(search_result, SearchQuery())
