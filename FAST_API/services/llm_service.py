import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv
import asyncio

# 분리된 서비스들 import
from services.intent_analyzer import IntentAnalyzer, IntentResult, ChatMessage
from services.product_filter import exact_match_filter, situation_filter
from services.recommendation_engine import RecommendationEngine, ToolResult
from services.weather_service import WeatherService
from services.location_service import LocationService
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
        self.weather_service = WeatherService()
        self.location_service = LocationService()

    async def analyze_intent_and_call_tool(self, user_input: str, chat_history: List[ChatMessage], available_products: List[Dict], db=None, user_id=None, latitude: Optional[float] = None, longitude: Optional[float] = None) -> LLMResponse:
        """사용자 입력을 분석하고 적절한 도구를 호출합니다."""

        # 1. 의도 분석
        intent_result = self.intent_analyzer.classify_intent(user_input, chat_history)

        print(f"의도 분류 결과: {intent_result.intent} (신뢰도: {intent_result.confidence})")

        # 2. 의도에 따른 도구 호출
        tool_result = None # tool_result 초기화
        try:
            if intent_result.intent == "weather":
                tool_result = await self.handle_weather_intent(intent_result, latitude, longitude)
            elif intent_result.intent == "search":
                tool_result = self.search_products(intent_result, available_products)
            elif intent_result.intent == "conversation":
                # Check if conversation query is actually about weather
                if any(word in intent_result.original_query.lower() for word in ["날씨", "weather", "비", "맑음", "흐림", "기온", "온도"]):
                    print("Weather detected in conversation intent - calling weather service")
                    tool_result = await self.handle_weather_intent(intent_result, latitude, longitude)
                else:
                    tool_result = self.recommendation_engine.conversation_recommendation(intent_result, available_products, db, user_id)
            else:  # general
                tool_result = self._handle_general_conversation(intent_result)
        except Exception as e:
            print(f"ERROR: Exception during tool call for intent {intent_result.intent}: {e}")
            # Return an LLMResponse indicating failure
            return LLMResponse(
                intent_result=intent_result,
                tool_result=ToolResult(success=False, message=f"도구 호출 중 오류가 발생했습니다: {e}", products=[], metadata={"error_during_tool_call": str(e)}),
                final_message=f"죄송합니다. 요청을 처리하는 중 오류가 발생했습니다: {e}",
                products=[]
            )

        # 3. 최종 응답 구성
        final_message = tool_result.message if tool_result else "죄송합니다. 요청을 처리할 수 없습니다."
        products = tool_result.products if tool_result else []

        return LLMResponse(
            intent_result=intent_result,
            tool_result=tool_result,
            final_message=final_message,
            products=products
        )

    async def handle_weather_intent(self, intent_result: IntentResult, latitude: Optional[float], longitude: Optional[float]) -> ToolResult:
        """날씨 관련 의도를 처리합니다."""
        locations = intent_result.extracted_info.get("locations", [])
        city_name = locations[0] if locations else None

        coords = None
        location_display_name = "현재 위치"

        # 1. 지역명이 명시적으로 추출된 경우 (가장 높은 우선순위)
        if city_name:
            location_display_name = f"'{city_name}'"
            coords = await self.location_service.get_coords_from_city_name(city_name)
            if not coords:
                return ToolResult(success=False, message=f"'{city_name}'의 위치를 찾을 수 없어요. 😥 지역명을 다시 확인해주시겠어요?", products=[], metadata={"error": "geocoding_failed"})

        # 2. 지역명은 없지만, 프론트에서 좌표를 준 경우 (현재 위치)
        elif latitude and longitude:
            city_name_from_coords = await self.location_service.get_city_name_from_coords(latitude, longitude)
            if city_name_from_coords:
                location_display_name = f"'{city_name_from_coords}'"
            else:
                location_display_name = "현재 위치"
            coords = {"latitude": latitude, "longitude": longitude}

        # 3. 좌표도, 지역명도 없는 경우
        else:
            return ToolResult(success=False, message="어느 지역의 날씨를 알려드릴까요? 🤔 도시 이름을 알려주시거나, 현재 위치의 날씨를 물어보세요!", products=[], metadata={"error": "no_location_provided"})

        # 날씨 정보 조회
        weather_data = await self.weather_service.get_current_weather(coords["latitude"], coords["longitude"])

        if "error" in weather_data:
            return ToolResult(success=False, message=f"죄송합니다. 날씨 정보를 가져오는 데 실패했습니다. ({weather_data['error']})", products=[], metadata={"error": "weather_api_failed"})

        temp = weather_data.get('temperature')
        sky = weather_data.get('sky_status')
        precip_type = weather_data.get('precipitation_type')
        precip_amount = weather_data.get('precipitation_amount')

        message = f"{location_display_name}의 날씨를 알려드릴게요! ☀️\n\n"
        if temp is not None:
            try:
                temp_float = float(temp)
                message += f"🌡️ **기온**: {temp}°C\n"
                # LLM을 사용하여 기온에 따른 날씨 상황 설명 추가
                weather_description = self._get_llm_weather_description(temp_float)
                message += f"✨ **날씨 상황**: {weather_description}\n"
            except ValueError:
                message += f"🌡️ **기온**: {temp}°C (온도 정보 처리 중 오류 발생)\n"
        if sky:
            message += f"☁️ **하늘**: {sky}\n"
        if precip_type and precip_type != "강수 없음":
            message += f"💧 **강수 형태**: {precip_type}\n"

        # 강수량이 있고, 0mm가 아닐 때만 표시
        if precip_amount and float(precip_amount) > 0:
            message += f"☔ **시간당 강수량**: {precip_amount}mm\n"

        

        return ToolResult(success=True, message=message, products=[], metadata={"weather_data": weather_data})

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

        # 키워드 매칭 시도
        for keyword, response in general_responses.items():
            if keyword in user_input_lower:
                return ToolResult(
                    success=True,
                    message=response,
                    products=[],
                    metadata={"conversation_type": "general"}
                )

        # 의류와 관련 없는 질문인지 확인
        clothing_keywords = ["옷", "의류", "패션", "스타일", "셔츠", "바지", "치마", "드레스", "코트", "재킷", "니트", "후드", "티셔츠", "청바지", "운동복", "정장", "데이트", "면접", "파티", "결혼식", "졸업식"]

        has_clothing_context = any(keyword in user_input_lower for keyword in clothing_keywords)

        if not has_clothing_context:
            # 의류와 관련 없는 질문에 대한 응답
            return ToolResult(
                success=True,
                message="저는 의류 추천 전문 챗봇이에요! 👗\n\n의류나 패션에 관한 질문을 해주시면 도움을 드릴 수 있어요.\n\n예시:\n• '파란색 셔츠 추천해줘'\n• '데이트룩 추천해줘'\n• '면접복 추천해줘'",
                products=[],
                metadata={"conversation_type": "general", "non_clothing_question": True}
            )

        # 기본 응답 (의류 관련이지만 구체적이지 않은 경우)
        return ToolResult(
            success=True,
            message="안녕하세요! 의류 추천을 도와드릴게요. 어떤 옷을 찾고 계신가요? 👕\n\n구체적으로 말씀해주시면 더 정확한 추천을 드릴 수 있어요!",
            products=[],
            metadata={"conversation_type": "general"}
        )

    def _get_llm_weather_description(self, temperature: float) -> str:
        """기온에 따라 날씨 상황을 설명합니다. 규칙 기반을 우선 사용하고, 필요시 LLM을 호출합니다."""
        
        # 규칙 기반 날씨 설명
        if temperature >= 35:
            return "폭염, 숨 막히는 더위"
        if temperature >= 30:
            return "한여름, 매우 더운 날씨"
        if temperature >= 28:
            return "본격적인 여름 날씨"
        if temperature >= 25:
            return "초여름 날씨"
        if temperature >= 20:
            return "따뜻한 봄 날씨"
        if temperature >= 15:
            return "선선한 가을 날씨"
        if temperature >= 10:
            return "쌀쌀한 가을 날씨"
        if temperature >= 5:
            return "쌀쌀한 초겨울 날씨"
        if temperature < 5:
            return "추운 겨울 날씨"

        # 규칙에 해당하지 않는 경우에만 LLM 호출 (현재 로직 상 모든 경우를 커버하므로 이 부분은 예비용)
        system_prompt = """당신은 날씨 전문가입니다.
        섭씨 온도가 주어지면, 해당 기온에 따른 날씨 상황을 간결하고 자연스러운 한국어 문구로 설명해주세요.
        예시:
        - 23도:過ごしやすい春の終わり
        - 18도:過ごしやすい秋の日
        """
        user_prompt = f"현재 기온: {temperature}°C"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=50
            )
            raw_llm_desc_content = response.choices[0].message.content.strip()
            print(f"DEBUG: Raw LLM weather description content: {raw_llm_desc_content}")
            return raw_llm_desc_content
        except Exception as e:
            print(f"LLM 날씨 설명 요청 오류: {e}")
            # 오류 발생 시 가장 안전한 기본값 반환
            return "날씨 정보를 확인 중입니다"
