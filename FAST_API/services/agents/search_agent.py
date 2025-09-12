"""
Search Intent Agent
구체적인 상품 검색 요청을 처리하는 에이전트
"""
import os
import json
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
    
    def process_search_request(self, user_input: str, available_products: List[Dict], 
                             context_info: Optional[Dict] = None,
                             db=None, user_id: Optional[int] = None) -> SearchAgentResult:
        """
        검색 요청 처리
        
        Args:
            user_input: 사용자 입력
            available_products: 검색할 상품 목록
            context_info: 컨텍스트 정보 (이전 추천 등)
        
        Returns:
            SearchAgentResult: 검색 결과
        """
        print(f"=== 🔍 Search Agent 시작 ===")
        print(f"사용자 입력: {user_input}")
        
        try:
            # 1. 검색 쿼리 구성 (내부 LLM 분석 사용)
            print(f"🔍 내부 LLM 분석 시작...")
            search_queries = self._analyze_search_request(user_input)
            print(f"✅ 분석 완료: {len(search_queries)}개 검색 쿼리 생성")
            
            # 2. 컨텍스트 기반 필터 구성
            context_filters = self._build_context_filters(context_info) if context_info else None
            
            # 3. 각 쿼리별로 상품 검색 실행
            all_products = []
            for i, search_query in enumerate(search_queries, 1):
                print(f"🔍 쿼리 {i}/{len(search_queries)} 실행:")
                print(f"   색상: {search_query.colors}")
                print(f"   카테고리: {search_query.categories}")
                print(f"   브랜드: {search_query.brands}")
                print(f"   가격: {search_query.price_range}")
                
                search_result = self.search_module.search_products(
                    query=search_query,
                    available_products=available_products,
                    context_filters=context_filters
                )
                print(f"   결과: {len(search_result.products)}개 상품 발견")
                all_products.extend(search_result.products)
            
            # 4. 통합된 검색 결과 생성
            search_result = type('SearchResult', (), {
                'products': all_products,
                'total_count': len(all_products),
                'search_summary': f"총 {len(all_products)}개 상품 발견",
                'applied_filters': f"복합 검색: {len(search_queries)}개 쿼리"
            })()
            
            # 4. 결과 메시지 생성
            if search_result.products:
                # LLM을 사용한 향상된 메시지 생성
                context_summaries = context_info.get("previous_summaries", []) if context_info else []
                # 첫 번째 쿼리를 대표로 사용 (메시지 생성용)
                representative_query = search_queries[0] if search_queries else SearchQuery()
                message = self.enhance_search_with_llm(user_input, search_result, context_summaries, representative_query)
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
    

    
    def _analyze_search_request(self, user_input: str) -> List[SearchQuery]:
        """사용자 입력을 분석하여 SearchQuery 리스트 생성 (내부 LLM 분석)"""
        system_prompt = """당신은 의류 검색 시스템의 쿼리 분석기입니다.
사용자의 검색 요청을 분석하여 검색 조건을 추출해주세요.

**카탈로그:**
- 후드티, 셔츠/블라우스, 긴소매, 반소매, 피케/카라, 니트/스웨터, 슬리브리스
- 데님팬츠, 트레이닝/조거팬츠, 코튼팬츠, 슈트팬츠/슬랙스, 숏팬츠, 카고팬츠
- 미니원피스, 미디원피스, 맥시원피스, 미니스커트, 미디스커트, 롱스커트
**카탈로그 내의 존재하지않는 카테고리 입력시 최대한 비슷한 카테고리로 선정해주세요.**
- 티셔츠 입력시 반소매로 처리해주세요.

**응답 형식 (JSON):**
[
    {
        "colors": ["추출된 색상들"],
        "categories": ["추출된 카테고리들"],
        "situations": ["추출된 상황들"],
        "styles": ["추출된 스타일들"],
        "brands": ["추출된 브랜드들"],
        "price_range": [최소가격, 최대가격] 또는 null
    },
    {
        "colors": ["추출된 색상들"],
        "categories": ["추출된 카테고리들"],
        "situations": ["추출된 상황들"],
        "styles": ["추출된 스타일들"],
        "brands": ["추출된 브랜드들"],
        "price_range": [최소가격, 최대가격] 또는 null
    }
]

**중요 규칙:**
1. 복합 검색 요청 시 (예: "검은색 티셔츠와 청바지") 각각을 개별적으로 추출
2. 색상: 빨간색, 파란색, 검은색, 흰색, 베이지, 네이비, 카키, 민트, 와인, 올리브 등
3. 카테고리: 카탈로그 내의 존재하는 카테고리만 넣어주세요.
4. 가격: "5만원 이하" → [0, 50000], "10만원 이상" → [100000, 9999999]
5. 브랜드: 나이키, 아디다스, 유니클로, ZARA, H&M 등
6. 상황: 데이트, 면접, 파티, 운동, 여행, 출근, 캐주얼 등
7. 스타일: 캐주얼, 정장, 스포티, 빈티지, 미니멀 등"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"검색 요청: {user_input}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # 배열 형태로 응답이 왔는지 확인
            if isinstance(result, list):
                # 복합 검색: 여러 개의 SearchQuery 생성
                search_queries = []
                for item in result:
                    search_query = SearchQuery(
                        colors=item.get("colors", []),
                        categories=item.get("categories", []),
                        situations=item.get("situations", []),
                        styles=item.get("styles", []),
                        locations=item.get("locations", []),
                        brands=item.get("brands", []),
                        price_range=item.get("price_range")
                    )
                    search_queries.append(search_query)
                return search_queries
            else:
                # 단일 검색: 하나의 SearchQuery 생성 (fallback)
                return [SearchQuery(
                    colors=result.get("colors", []),
                    categories=result.get("categories", []),
                    situations=result.get("situations", []),
                    styles=result.get("styles", []),
                    locations=result.get("locations", []),
                    brands=result.get("brands", []),
                    price_range=result.get("price_range")
                )]
            
        except Exception as e:
            print(f"검색 요청 분석 오류: {e}")
            # 오류 시 기본 SearchQuery 반환
            return SearchQuery()
    
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
    
    
    def build_system_prompt(self, user_input: str, search_result: SearchResult, 
                           context_summaries: List[str], query: SearchQuery = None) -> str:
        """LLM 시스템 프롬프트 생성 - 의미적으로 연결된 조합 지원"""
        
        # 컨텍스트 요약이 있으면 활용
        context_str = ""
        if context_summaries:
            context_str = f"\n이전 대화 요약: {' | '.join(context_summaries[-3:])}"
        
        # 검색 쿼리 정보 추가 (필터링 조건)
        query_info = ""
        if query:
            query_parts = []
            if query.colors:
                query_parts.append(f"색상: {', '.join(query.colors)}")
            if query.categories:
                query_parts.append(f"카테고리: {', '.join(query.categories)}")
            if query.situations:
                query_parts.append(f"상황: {', '.join(query.situations)}")
            if query.styles:
                query_parts.append(f"스타일: {', '.join(query.styles)}")
            if query.brands:
                query_parts.append(f"브랜드: {', '.join(query.brands)}")
            if query.price_range:
                min_price, max_price = query.price_range
                if min_price and max_price:
                    query_parts.append(f"가격대: {min_price:,}원 ~ {max_price:,}원")
                elif min_price:
                    query_parts.append(f"최소가격: {min_price:,}원 이상")
                elif max_price:
                    query_parts.append(f"최대가격: {max_price:,}원 이하")
            
            if query_parts:
                query_info = f"\n**검색 조건:** {', '.join(query_parts)}"
        
        # 실제 상품 정보를 프롬프트에 포함
        products_info = ""
        for i, product in enumerate(search_result.products, 1):
            product_name = product.get('상품명', '상품명 없음')
            brand = product.get('한글브랜드명', '브랜드 없음')
            price = product.get('원가', 0)
            
            products_info += f"\n{i}. 상품명: {product_name}\n   브랜드: {brand}\n   가격: {price:,}원\n"
        
        return f"""당신은 친근하고 전문적인 의류 상담사입니다.
사용자의 검색 요청에 맞는 상품들을 구체적이고 유용하게 설명해주세요.

**사용자 검색 요청:** {user_input}
**검색 조건:**{query_info}
**검색 결과:** {len(search_result.products)}개 상품 발견
{context_str}

**실제 상품 정보:**
{products_info}

**응답 형식:**
출력은 설명 없이 **순수 JSON만**. 형식:

{{
  "recommendations": [
    {{
      "item": "상품명",
      "style": "스타일",
      "color": "색상",
      "reason": "검색 조건과 연결된 구체적인 추천 이유"
    }}
  ]
}}

**중요 규칙:**
- 반드시 위에 제공된 실제 상품명과 브랜드를 그대로 사용하세요
- 가상의 상품명이나 브랜드를 만들어내지 마세요
- item은 실제 상품명을 사용하세요
- style과 color는 상품의 실제 특성을 반영하세요
- **reason은 반드시 검색 조건과 연결하여 설명하세요:**
  * 색상 조건이 있으면: "요청하신 [색상]으로 [스타일]한 룩 연출"
  * 브랜드 조건이 있으면: "[브랜드]의 [특징]으로 [장점]"
  * 가격대 조건이 있으면: "요청하신 [가격대]에 맞는 [가격 특징]"
  * 상황 조건이 있으면: "[상황]에 적합한 [스타일]한 [아이템]"
  * 여러 조건이 있으면: "요청하신 [색상] [브랜드] [가격대]에 맞는 [종합 설명]"

**예시:**
- "요청하신 빨간색으로 화려하면서도 캐주얼한 룩 완성"
- "나이키의 프리미엄 품질로 스포티하면서도 세련된 느낌"
- "요청하신 5만원 이하 가격대에 맞는 합리적인 가격의 데일리 아이템"
- "데이트 상황에 적합한 우아하면서도 섹시한 미니스커트" """

    def enhance_search_with_llm(self, user_input: str, search_result: SearchResult, 
                               context_summaries: List[str], query: SearchQuery = None) -> str:
        """
        LLM을 사용하여 검색 결과를 향상시킨 메시지 생성
        """
        if not search_result.products:
            return search_result.search_summary
        
        try:
            # 개선된 프롬프트 사용
            system_prompt = self.build_system_prompt(user_input, search_result, context_summaries, query)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"위 조건으로 {len(search_result.products)}개 상품을 찾았습니다. JSON 형태로 추천 정보를 반환해주세요."}
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            raw_llm_response_content = response.choices[0].message.content
            print(f"DEBUG: Raw LLM response content: {raw_llm_response_content}")
            
            # JSON 파싱 및 메시지 생성
            recommended_items = json.loads(raw_llm_response_content)
            print(f"DEBUG: Parsed recommended_items: {recommended_items}")
            
            # 새로운 JSON 구조로 메시지 생성
            return self._create_enhanced_message(user_input, search_result, recommended_items)
            
        except Exception as e:
            print(f"LLM 향상 메시지 생성 오류: {e}")
            # 오류 시 기본 메시지 반환
            return self.search_module.generate_search_message(search_result, SearchQuery())
    
    def _create_enhanced_message(self, user_input: str, search_result: SearchResult, 
                                recommended_items: Dict) -> str:
        """LLM 응답을 바탕으로 향상된 메시지 생성"""
        
        # 새로운 JSON 구조에서 추천 데이터 추출
        recommendations = recommended_items.get("recommendations", [])
        
        if recommendations:
            # 새로운 구조: 의미적으로 연결된 조합
            message = f"안녕하세요! '{user_input}' 조건에 맞는 {len(search_result.products)}개 상품을 찾았어요! 😊\n\n"
            message += f"🎯 **검색 결과 상품 추천**\n"
            
            for i, rec in enumerate(recommendations, 1):
                item = rec.get("item", "")
                style = rec.get("style", "")
                color = rec.get("color", "")
                reason = rec.get("reason", "")
                
                message += f"**{i}. {item}**\n"
                if style:
                    message += f"   🎨 스타일: {style}\n"
                if color:
                    message += f"   🌈 색상: {color}\n"
                if reason:
                    message += f"   💡 추천 이유: {reason}\n"
                message += "\n"
            
            return message
        else:
            # 기존 구조 지원 (fallback)
            return self.search_module.generate_search_message(search_result, SearchQuery())
