import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

# 분리된 서비스들 import
from services.intent_analyzer import IntentAnalyzer, IntentResult, ChatMessage
from services.product_filter import exact_match_filter, situation_filter
from services.recommendation_engine import RecommendationEngine, ToolResult
from utils.safe_utils import safe_lower

load_dotenv()

@dataclass
class LLMResponse:
    intent_result: IntentResult
    tool_result: Optional[ToolResult]
    final_message: str
    products: List[Dict]

class LLMService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
        self.intent_analyzer = IntentAnalyzer()
        self.recommendation_engine = RecommendationEngine()
        
    def analyze_intent_and_call_tool(self, user_input: str, chat_history: List[ChatMessage], available_products: List[Dict]) -> LLMResponse:
        """사용자 입력을 분석하고 적절한 도구를 호출합니다."""
        
        # 1. 의도 분석
        intent_result = self.intent_analyzer.classify_intent(user_input, chat_history)
        
        print(f"의도 분류 결과: {intent_result.intent} (신뢰도: {intent_result.confidence})")
        
        # 2. 의도에 따른 도구 호출
        if intent_result.intent == "search":
            tool_result = self.search_products(intent_result, available_products)
        elif intent_result.intent == "conversation":
            tool_result = self.recommendation_engine.conversation_recommendation(intent_result, available_products)
        else:  # general
            tool_result = self._handle_general_conversation(intent_result)
        
        # 3. 최종 응답 구성
        final_message = tool_result.message if tool_result else "죄송합니다. 요청을 처리할 수 없습니다."
        products = tool_result.products if tool_result else []
        
        return LLMResponse(
            intent_result=intent_result,
            tool_result=tool_result,
            final_message=final_message,
            products=products
        )
    
    def search_products(self, intent_result: IntentResult, available_products: List[Dict]) -> ToolResult:
        """상품 검색을 수행합니다."""
        
        print(f"=== 상품 검색 시작 ===")
        print(f"검색 쿼리: {intent_result.original_query}")
        
        # 정확 매칭 필터링 사용
        matched_products = exact_match_filter(intent_result.original_query, available_products)
        
        if not matched_products:
            return ToolResult(
                success=False,
                message=f"'{intent_result.original_query}'에 맞는 상품을 찾지 못했습니다. 다른 조건으로 검색해보세요.",
                products=[],
                metadata={"error": "no_matched_products"}
            )
        
        # 검색 결과 메시지 생성
        message = f"'{intent_result.original_query}' 검색 결과입니다! 🔍\n\n"
        
        # 상의/하의 분류
        top_products = []
        bottom_products = []
        
        for product in matched_products:
            if product.get("is_top", False):
                top_products.append(product)
            elif product.get("is_bottom", False):
                bottom_products.append(product)
        
        # 상의 섹션
        if top_products:
            message += "👕 **상의**\n"
            for i, product in enumerate(top_products[:3], 1):
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                # 원가 우선 사용
                price = product.get('원가', 0)
                
                message += f"**{i}. {product_name}**\n"
                message += f"   📍 브랜드: {brand}\n"
                if price:
                    message += f"   💰 가격: {price:,}원\n"
                message += "\n"
        
        # 하의 섹션
        if bottom_products:
            message += "👖 **하의**\n"
            for i, product in enumerate(bottom_products[:3], 1):
                product_name = product.get('상품명', '상품명 없음')
                brand = product.get('한글브랜드명', '브랜드 없음')
                # 원가 우선 사용
                price = product.get('원가', 0)
                
                message += f"**{i}. {product_name}**\n"
                message += f"   📍 브랜드: {brand}\n"
                if price:
                    message += f"   💰 가격: {price:,}원\n"
                message += "\n"
        
        return ToolResult(
            success=True,
            message=message,
            products=matched_products,
            metadata={"search_query": intent_result.original_query}
        )
    
    def _handle_general_conversation(self, intent_result: IntentResult) -> ToolResult:
        """일반적인 대화를 처리합니다."""
        
        general_responses = {
            "안녕": "안녕하세요! 👋 의류 추천을 도와드릴게요. 어떤 옷을 찾고 계신가요?",
            "도움말": "저는 의류 추천 챗봇입니다! 🛍️\n\n• 구체적인 검색: '파란색 셔츠 추천해줘'\n• 상황별 추천: '데이트룩 추천해줘'\n• 일반 대화도 가능해요!",
            "감사": "천만에요! 😊 더 필요한 것이 있으시면 언제든 말씀해주세요.",
            "고마워": "천만에요! 😊 더 필요한 것이 있으시면 언제든 말씀해주세요."
        }
        
        user_input_lower = safe_lower(intent_result.original_query)
        
        for keyword, response in general_responses.items():
            if keyword in user_input_lower:
                return ToolResult(
                    success=True,
                    message=response,
                    products=[],
                    metadata={"conversation_type": "general"}
                )
        
        # 기본 응답
        return ToolResult(
            success=True,
            message="안녕하세요! 의류 추천을 도와드릴게요. 어떤 옷을 찾고 계신가요? 👕",
            products=[],
            metadata={"conversation_type": "general"}
        )