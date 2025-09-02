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
                                   context_summaries: Optional[List[str]] = None,
                                   db=None, user_id=None) -> ConversationAgentResult:
        """
        대화형 추천 요청 처리
        
        Args:
            user_input: 사용자 입력
            extracted_info: 추출된 정보 (상황, 스타일 등)
            available_products: 추천할 상품 목록
            context_summaries: 이전 대화 요약들
            db: 데이터베이스 세션
            user_id: 사용자 ID
        
        Returns:
            ConversationAgentResult: 추천 결과
        """
        print(f"=== Conversation Agent 시작 ===")
        print(f"사용자 입력: {user_input}")
        print(f"추출된 정보: {extracted_info}")
        print(f"컨텍스트 요약: {context_summaries}")
        
        try:
            # 1. 날씨 관련 요청인지 확인
            weather_context = self._check_weather_context(user_input, extracted_info)
            
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
            
            # 6. 추천 결과 저장 (옵션)
            if db and user_id and balanced_products:
                self._save_recommendations_to_db(db, user_id, user_input, balanced_products)
            
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
    
    def _check_weather_context(self, user_input: str, extracted_info: Dict) -> Optional[str]:
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
            "reason": "추천 이유"
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
   - 상의: 후드티, 셔츠블라우스, 긴소매, 반소매, 피케카라, 니트스웨터, 슬리브리스, 애슬레저
   - 하의: 데님 팬츠, 트레이닝/조거 팬츠, 코튼 팬츠, 슈트 팬츠/슬랙스, 숏 팬츠, 레깅스, 카고팬츠 
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
        """추천 스펙을 검색 쿼리들로 변환 (DB 카테고리에 맞게 매핑)"""
        queries = []
        
        # 아이템 타입을 실제 DB 카테고리/키워드로 매핑 (확장됨)
        type_mapping = {
            # 상의 관련 - 니트/스웨터류
            "라운드넥 니트": ["니트", "스웨터", "knit", "sweater", "니트스웨터"],
            "니트": ["니트", "스웨터", "knit", "sweater", "니트스웨터"],
            "스웨터": ["니트", "스웨터", "knit", "sweater", "니트스웨터"],
            "카디건": ["카디건", "니트", "cardigan"],
            
            # 상의 관련 - 아우터류
            "가벼운 트렌치코트": ["코트", "재킷", "아우터", "coat", "jacket", "트렌치"],
            "트렌치코트": ["코트", "재킷", "아우터", "coat", "jacket", "트렌치"],
            "재킷": ["재킷", "코트", "아우터", "jacket", "coat"],
            "코트": ["코트", "재킷", "아우터", "coat", "jacket"],
            "블레이저": ["블레이저", "재킷", "정장", "blazer"],
            
            # 상의 관련 - 셔츠류
            "셔츠": ["셔츠", "블라우스", "shirt", "blouse", "셔츠블라우스"],
            "블라우스": ["블라우스", "셔츠", "blouse", "shirt", "셔츠블라우스"],
            "와이셔츠": ["셔츠", "와이셔츠", "정장셔츠", "shirt"],
            
            # 상의 관련 - 티셔츠류
            "티셔츠": ["티셔츠", "반팔", "tshirt", "t-shirt", "반소매"],
            "반팔 티셔츠": ["티셔츠", "반팔", "tshirt", "t-shirt", "반소매"],
            "긴팔 티셔츠": ["티셔츠", "긴팔", "tshirt", "긴소매"],
            
            # 상의 관련 - 후드/맨투맨
            "후드티": ["후드", "후드티", "hood", "hoodie"],
            "맨투맨": ["맨투맨", "스웨트셔츠", "sweat"],
            "슬리브리스": ["슬리브리스", "민소매", "나시", "tank", "sleeveless"],
            
            # 하의 관련 - 청바지/데님
            "슬림핏 청바지": ["청바지", "데님", "jeans", "denim", "데님팬츠"],
            "청바지": ["청바지", "데님", "jeans", "denim", "데님팬츠"],
            "데님 팬츠": ["청바지", "데님", "jeans", "denim", "데님팬츠"],
            "스키니진": ["청바지", "데님", "스키니", "skinny", "jeans"],
            
            # 하의 관련 - 팬츠류
            "면 치노 팬츠": ["팬츠", "바지", "치노", "chino", "pants", "코튼팬츠"],
            "치노팬츠": ["팬츠", "바지", "치노", "chino", "pants", "코튼팬츠"],
            "코튼 팬츠": ["팬츠", "바지", "코튼", "cotton", "pants", "코튼팬츠"],
            "와이드 팬츠": ["팬츠", "바지", "와이드", "wide", "pants"],
            "슬랙스": ["슬랙스", "정장바지", "slacks", "dress pants", "슈트팬츠슬랙스"],
            "조거팬츠": ["조거", "트레이닝", "jogger", "training", "트레이닝조거팬츠"],
            "트레이닝 팬츠": ["조거", "트레이닝", "jogger", "training", "트레이닝조거팬츠"],
            
            # 하의 관련 - 짧은 하의
            "반바지": ["반바지", "숏팬츠", "shorts", "short", "숏팬츠"],
            "숏팬츠": ["반바지", "숏팬츠", "shorts", "short", "숏팬츠"],
            
            # 여성 전용
            "스커트": ["스커트", "skirt"],
            "미니스커트": ["스커트", "미니", "skirt", "mini"],
            "원피스": ["원피스", "dress"],
            "미니원피스": ["원피스", "미니", "dress", "mini"],
            "레깅스": ["레깅스", "leggings"]
        }
        
        for rec in recommendation_spec.get("recommendations", []):
            category = rec.get("category", "")
            color = rec.get("color", "")
            item_type = rec.get("type", "")
            
            # 필수 정보가 있는 경우만 쿼리 생성
            if category and color and item_type:
                # 아이템 타입을 DB 친화적인 키워드로 변환
                mapped_keywords = type_mapping.get(item_type, [item_type])
                
                # 기본 카테고리 키워드 추가
                if category == "상의":
                    mapped_keywords.extend(["상의", "탑", "top"])
                elif category == "하의":
                    mapped_keywords.extend(["하의", "바텀", "bottom", "바지", "팬츠"])
                
                query = SearchQuery(
                    colors=[color],
                    categories=mapped_keywords,  # 매핑된 키워드들을 카테고리로 사용
                    situations=[],
                    styles=[]
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
    
    def _save_recommendations_to_db(self, db, user_id: int, query: str, products: List[Dict]):
        """추천 결과를 데이터베이스에 저장 - 챗봇 라우터에서만 저장하도록 비활성화"""
        # 챗봇 라우터에서만 추천을 저장하도록 비활성화
        # 중복 저장 방지를 위해 ConversationAgent에서는 저장하지 않음
        print("ℹ️ ConversationAgent: 추천 저장은 챗봇 라우터에서 처리됩니다.")
        return
        
        # 기존 코드 (주석 처리)
        """
        try:
            from crud.recommendation_crud import create_multiple_recommendations, get_user_recommendations
            
            # 최근 추천 기록 조회하여 중복 체크
            recent_recommendations = get_user_recommendations(db, user_id, limit=20)
            recent_item_ids = {rec.item_id for rec in recent_recommendations}
            
            recommendations_data = []
            for product in products:
                item_id = product.get("상품코드", 0)
                if item_id and item_id not in recent_item_ids:
                    recommendations_data.append({
                        "item_id": item_id,
                        "query": query,
                        "reason": "상황별 추천"
                    })
                    recent_item_ids.add(item_id)  # 중복 방지를 위해 추가
            
            if recommendations_data:
                create_multiple_recommendations(db, user_id, recommendations_data)
                print(f"✅ 추천 결과 {len(recommendations_data)}개를 데이터베이스에 저장했습니다.")
            else:
                print("⚠️ 저장할 추천 결과가 없습니다 (중복 제거 후).")
                
        except Exception as e:
            print(f"❌ 추천 결과 저장 중 오류: {e}")
            
            # 저장 실패해도 추천은 계속 진행
        """