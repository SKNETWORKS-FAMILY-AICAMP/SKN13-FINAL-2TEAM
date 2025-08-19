import json
import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
import os
from dotenv import load_dotenv
from utils.safe_utils import safe_lower, safe_str

load_dotenv()

@dataclass
class RecommendationItem:
    category: str
    color: str
    type: str
    reason: str
    matched_product: Optional[Dict] = None
    search_query_used: str = ""

@dataclass
class ToolResult:
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

class RecommendationEngine:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    
    def conversation_recommendation(self, intent_result, available_products: List[Dict]) -> ToolResult:
        """개선된 대화 기반 상황별 추천을 수행합니다."""
        
        print(f"=== 1. 컨벌세이션 인텐트 확인 ===")
        print(f"인텐트: {intent_result.intent}")
        print(f"신뢰도: {intent_result.confidence}")
        print(f"추출된 정보: {intent_result.extracted_info}")
        
        # 2. LLM에 상황별 추천 JSON 요청
        print(f"=== 2. LLM 상황별 추천 JSON 요청 ===")
        llm_recommendations = self._get_situation_recommendations(intent_result)
        
        if not llm_recommendations:
            return self._fallback_recommendation(intent_result, available_products)
        
        print(f"LLM 추천 결과: {len(llm_recommendations.get('recommendations', []))}개 아이템")
        
        # 3. 각 추천 아이템별로 상품 매칭
        print(f"=== 3. 추천 아이템별 상품 매칭 ===")
        matched_items = []
        
        for i, rec in enumerate(llm_recommendations.get("recommendations", []), 1):
            print(f"\n--- 추천 아이템 {i} 처리 ---")
            
            # 필수 정보 확인 (색상, 카테고리, 타입 모두 있어야 함)
            color = rec.get("color", "").strip()
            category = rec.get("category", "").strip()
            item_type = rec.get("type", "").strip()
            
            # 필수 조건: 색상, 카테고리, 타입 모두 존재해야 함
            if not color or not category or not item_type:
                print(f"❌ 필수 정보 부족으로 건너뜀: color='{color}', category='{category}', type='{item_type}'")
                continue
            
            # 카테고리 검증 (상의/하의만 허용)
            if category not in ["상의", "하의"]:
                print(f"❌ 잘못된 카테고리로 건너뜀: '{category}' (상의/하의만 허용)")
                continue
            
            print(f"✅ 검증 통과: {category} - {color} {item_type}")
            
            # 상품 매칭 시도
            matched_item = self._match_product_for_recommendation(rec, available_products)
            
            if matched_item.matched_product:
                matched_items.append(matched_item)
        
        # 매칭된 아이템이 없으면 실패 반환
        if not matched_items:
            print("❌ 매칭된 아이템이 없습니다.")
            return ToolResult(
                success=False,
                message=f"'{intent_result.original_query}'에 맞는 상품을 찾지 못했습니다. 다른 조건으로 검색해보세요.",
                products=[],
                metadata={"error": "no_matched_items"}
            )
        
        # 4. 상의/하의 균형 맞추기
        print(f"=== 4. 상의/하의 균형 맞추기 ===")
        balanced_products = self._balance_products_from_matched_items(matched_items, available_products)
        
        # 5. 최종 메시지 생성 (reason과 함께)
        print(f"=== 5. 최종 메시지 생성 ===")
        final_message = self._generate_final_message(
            llm_recommendations, 
            matched_items, 
            balanced_products, 
            intent_result.original_query
        )
        
        # 6. 챗 로그용 메타데이터 준비 (매칭된 아이템만)
        from services.chat_logger import prepare_chat_log_data
        matched_items_with_products = [item for item in matched_items if item.matched_product is not None]
        chat_log_data = prepare_chat_log_data(matched_items_with_products, balanced_products)
        
        print(f"최종 추천 상품 수: {len(balanced_products)}")
        
        return ToolResult(
            success=len(balanced_products) > 0,
            message=final_message,
            products=balanced_products,
            metadata={
                "styling_tips": llm_recommendations.get("styling_tips", ""),
                "recommendations": llm_recommendations.get("recommendations", []),
                "matched_items": [
                    {
                        "category": item.category,
                        "color": item.color,
                        "type": item.type,
                        "reason": item.reason,
                        "search_query_used": item.search_query_used,
                        "product_matched": item.matched_product is not None
                    }
                    for item in matched_items if item.matched_product is not None
                ],
                "chat_log_data": chat_log_data
            }
        )
    
    def _get_situation_recommendations(self, intent_result) -> Dict:
        """LLM으로부터 상황별 추천 JSON을 받아옵니다."""
        
        system_prompt = """당신은 의류 스타일링 전문가입니다.
사용자의 상황과 요청에 맞는 구체적인 의상 스펙을 제안해주세요.

사용자 요청 분석:
- 상황: {situations}
- 스타일: {styles}
- 색상: {colors}
- 키워드: {keywords}

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
    "styling_tips": "전체적인 스타일링 팁"
}}

규칙:
1. 상의 2개, 하의 2개 추천
2. 색상 조합이 조화롭게
3. 상황에 맞는 스타일
4. 구체적인 의류 종류 명시 (셔츠, 니트, 청바지 등)"""

        # 추출된 정보에서 상황과 스타일 추출
        extracted_info = intent_result.extracted_info
        situations = ", ".join(extracted_info.get("situations", []))
        styles = ", ".join(extracted_info.get("styles", []))
        colors = ", ".join(extracted_info.get("colors", []))
        keywords = ", ".join(extracted_info.get("keywords", []))
        
        user_prompt = f"사용자 요청: {intent_result.original_query}"
        
        messages = [
            {"role": "system", "content": system_prompt.format(
                situations=situations,
                styles=styles,
                colors=colors,
                keywords=keywords
            )},
            {"role": "user", "content": user_prompt}
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
            
            return result
            
        except Exception as e:
            print(f"LLM 추천 요청 오류: {e}")
            return None
    
    def _match_product_for_recommendation(self, recommendation: Dict, available_products: List[Dict]) -> RecommendationItem:
        """추천 아이템에 맞는 실제 상품을 찾습니다."""
        
        category = recommendation.get("category", "")
        color = recommendation.get("color", "")
        item_type = recommendation.get("type", "")
        reason = recommendation.get("reason", "")
        
        # 검색 쿼리 구성
        search_query = f"{color} {item_type}"
        
        # 상품 매칭 로직
        matched_product = None
        best_score = 0
        
        for product in available_products:
            score = 0
            
            # 카테고리 매칭
            product_category = product.get("대분류", "")
            if category == "상의" and product_category in ["상의", "탑", "TOP"]:
                score += 3
            elif category == "하의" and product_category in ["하의", "바텀", "BOTTOM"]:
                score += 3
            
            # 색상 매칭
            product_color = safe_lower(product.get("색상", ""))
            if safe_lower(color) in product_color:
                score += 2
            
            # 타입 매칭
            product_name = safe_lower(product.get("상품명", ""))
            if safe_lower(item_type) in product_name:
                score += 2
            
            # 브랜드명에서도 확인
            brand_name = safe_lower(product.get("한글브랜드명", ""))
            if safe_lower(item_type) in brand_name:
                score += 1
            
            if score > best_score:
                best_score = score
                matched_product = product
        
        return RecommendationItem(
            category=category,
            color=color,
            type=item_type,
            reason=reason,
            matched_product=matched_product,
            search_query_used=search_query
        )
    
    def _balance_products_from_matched_items(self, matched_items: List[RecommendationItem], available_products: List[Dict]) -> List[Dict]:
        """매칭된 아이템들에서 상의/하의 균형을 맞춰 최종 상품 목록을 구성합니다."""
        
        top_items = [item for item in matched_items if item.category == "상의"]
        bottom_items = [item for item in matched_items if item.category == "하의"]
        
        final_products = []
        
        # 상의/하의 균형 맞추기 (최대 4개)
        if len(top_items) >= 2 and len(bottom_items) >= 2:
            # 상의 2개, 하의 2개
            selected_tops = random.sample(top_items, 2)
            selected_bottoms = random.sample(bottom_items, 2)
        elif len(top_items) >= 2:
            # 상의 2개, 하의 1-2개
            selected_tops = random.sample(top_items, 2)
            selected_bottoms = random.sample(bottom_items, min(2, len(bottom_items)))
        elif len(bottom_items) >= 2:
            # 상의 1-2개, 하의 2개
            selected_tops = random.sample(top_items, min(2, len(top_items)))
            selected_bottoms = random.sample(bottom_items, 2)
        else:
            # 각각 1-2개씩
            selected_tops = random.sample(top_items, min(2, len(top_items)))
            selected_bottoms = random.sample(bottom_items, min(2, len(bottom_items)))
        
        final_products.extend([item.matched_product for item in selected_tops if item.matched_product])
        final_products.extend([item.matched_product for item in selected_bottoms if item.matched_product])
        
        # 중복 제거
        seen_ids = set()
        unique_products = []
        for product in final_products:
            product_id = product.get("상품코드", "")
            if product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_products.append(product)
        
        return unique_products[:4]  # 최대 4개
    
    def _generate_final_message(self, llm_recommendations: Dict, matched_items: List[RecommendationItem], 
                              balanced_products: List[Dict], original_query: str) -> str:
        """최종 추천 메시지를 생성합니다."""
        
        message = f"'{original_query}'에 맞는 스타일을 추천해드릴게요! ✨\n\n"
        
        # 실제 선택된 상품들만 메시지에 포함
        selected_products = []
        for product in balanced_products:
            # 해당 상품에 매칭된 아이템 찾기
            matched_item = None
            for item in matched_items:
                if item.matched_product and item.matched_product.get("상품코드") == product.get("상품코드"):
                    matched_item = item
                    break
            
            selected_products.append({
                "product": product,
                "matched_item": matched_item,
                "category": matched_item.category if matched_item else "기타"
            })
        
        # 상의/하의 분류
        top_products = [item for item in selected_products if item["category"] == "상의"]
        bottom_products = [item for item in selected_products if item["category"] == "하의"]
        
        # 상의 섹션
        if top_products:
            message += "👕 **상의 추천**\n"
            for i, item_info in enumerate(top_products, 1):
                product = item_info['product']
                matched_item = item_info['matched_item']
                
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                # 원가 우선 사용
                price = product.get('원가', 0)
                
                message += f"**{i}. {product_name}**\n"
                message += f"   📍 브랜드: {brand}\n"
                if price:
                    message += f"   💰 가격: {price:,}원\n"
                
                if matched_item and matched_item.reason:
                    message += f"   ✨ 추천 이유: {matched_item.reason}\n"
                message += "\n"
        
        # 하의 섹션
        if bottom_products:
            message += "👖 **하의 추천**\n"
            for i, item_info in enumerate(bottom_products, 1):
                product = item_info['product']
                matched_item = item_info['matched_item']
                
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                # 원가 우선 사용
                price = product.get('원가', 0)
                
                message += f"**{i}. {product_name}**\n"
                message += f"   📍 브랜드: {brand}\n"
                if price:
                    message += f"   💰 가격: {price:,}원\n"
                
                if matched_item and matched_item.reason:
                    message += f"   ✨ 추천 이유: {matched_item.reason}\n"
                message += "\n"
        
        # 스타일링 팁 추가
        if llm_recommendations.get("styling_tips"):
            message += f"💡 **스타일링 팁**\n{llm_recommendations['styling_tips']}"
        
        return message
    
    def _fallback_recommendation(self, intent_result, available_products: List[Dict]) -> ToolResult:
        """LLM 추천이 실패했을 때 기본 추천을 제공합니다."""
        
        # 랜덤으로 4개 상품 선택
        if len(available_products) >= 4:
            selected_products = random.sample(available_products, 4)
        else:
            selected_products = available_products
        
        message = f"'{intent_result.original_query}'에 대한 추천 상품입니다! 🛍️\n\n"
        
        for i, product in enumerate(selected_products, 1):
            product_name = product.get('상품명', '상품명 없음')
            brand = product.get('한글브랜드명', '브랜드 없음')
            price = product.get('원가', 0)
            
            message += f"**{i}. {product_name}**\n"
            message += f"   📍 브랜드: {brand}\n"
            if price:
                message += f"   💰 가격: {price:,}원\n"
            message += "\n"
        
        return ToolResult(
            success=len(selected_products) > 0,
            message=message,
            products=selected_products,
            metadata={"fallback": True}
        )
