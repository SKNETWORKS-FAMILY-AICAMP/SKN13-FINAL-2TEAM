"""
Weather Intent Agent
날씨 관련 요청을 처리하는 에이전트
"""
import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 의류 카탈로그 정의
CATALOG = {
    "tops":    ["후드티","셔츠/블라우스","긴소매","반소매","피케/카라","니트/스웨터","슬리브리스"],
    "bottoms": ["데님팬츠","트레이닝/조거팬츠","코튼팬츠","슬랙스/슈트팬츠","숏팬츠","카고팬츠"],
    "dresses": ["미니원피스","미디원피스","맥시원피스"],
    "skirts":  ["미니스커트","미디스커트","롱스커트"],
}

@dataclass
class WeatherAgentResult:
    """Weather Agent 결과"""
    success: bool
    message: str
    products: List[Dict]
    metadata: Dict

class WeatherAgent:
    """날씨 에이전트"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    
    async def process_weather_request(self, user_input: str, extracted_info: Dict,
                                    latitude: Optional[float] = None,
                                    longitude: Optional[float] = None,
                                    user_gender: str = "남성") -> WeatherAgentResult:
        """
        날씨 요청 처리 (의류 추천 포함)
        
        Args:
            user_input: 사용자 입력
            extracted_info: 추출된 정보 (지역명 등)
            latitude: 위도
            longitude: 경도
            user_gender: 사용자 성별
        
        Returns:
            WeatherAgentResult: 날씨 정보 + 의류 추천 결과
        """
        print(f"=== Weather Agent 시작 ===")
        print(f"사용자 입력: {user_input}")
        print(f"추출된 정보: {extracted_info}")
        
        try:
            # extracted_info가 비어있으면 내부 분석 수행
            if not extracted_info:
                extracted_info = self._analyze_weather_request(user_input)
            
            # 지역 정보 처리
            locations = extracted_info.get("locations", [])
            city_name = locations[0] if locations else None
            
            coords = None
            location_display_name = "현재 위치"
            
            # 1. 지역명이 명시적으로 추출된 경우
            if city_name:
                location_display_name = f"'{city_name}'"
                coords = await self._get_coords_from_city_name(city_name)
                if not coords:
                    return WeatherAgentResult(
                        success=False,
                        message=f"'{city_name}'의 위치를 찾을 수 없어요. 😥 지역명을 다시 확인해주시겠어요?",
                        products=[],
                        metadata={"error": "geocoding_failed", "agent_type": "weather"}
                    )
            
            # 2. 지역명은 없지만 좌표가 있는 경우
            elif latitude and longitude:
                city_name_from_coords = await self._get_city_name_from_coords(latitude, longitude)
                if city_name_from_coords:
                    location_display_name = f"'{city_name_from_coords}'"
                else:
                    location_display_name = "현재 위치"
                coords = {"latitude": latitude, "longitude": longitude}
            
            # 3. 좌표도, 지역명도 없는 경우
            else:
                return WeatherAgentResult(
                    success=False,
                    message="어느 지역의 날씨를 알려드릴까요? 🤔 도시 이름을 알려주시거나, 현재 위치의 날씨를 물어보세요!",
                    products=[],
                    metadata={"error": "no_location_provided", "agent_type": "weather"}
                )
            
            # 날씨 정보 조회 (고급 기능 사용)
            weather_data = await self._get_advanced_weather(coords["latitude"], coords["longitude"])
            
            if "error" in weather_data:
                return WeatherAgentResult(
                    success=False,
                    message=f"죄송합니다. 날씨 정보를 가져오는 데 실패했습니다. ({weather_data['error']})",
                    products=[],
                    metadata={"error": "weather_api_failed", "agent_type": "weather"}
                )
            
            # 날씨 메시지 생성
            message = self._generate_weather_message(location_display_name, weather_data)
            
            # LLM에서 추출한 상황 정보 가져오기
            situations = extracted_info.get("situations", [])
            
            # 의류 추천 추가 (상황 정보 포함)
            enhanced_message, recommended_products = await self._enhance_weather_with_clothing(
                message, weather_data, user_gender, location_display_name, situations
            )
            
            return WeatherAgentResult(
                success=True,
                message=enhanced_message,
                products=recommended_products,
                metadata={
                    "weather_data": weather_data,
                    "location": location_display_name,
                    "agent_type": "weather",
                    "has_clothing_recommendations": len(recommended_products) > 0
                }
            )
            
        except Exception as e:
            print(f"Weather Agent 오류: {e}")
            return WeatherAgentResult(
                success=False,
                message="날씨 정보를 가져오는 중 오류가 발생했습니다. 다시 시도해주세요.",
                products=[],
                metadata={"error": str(e), "agent_type": "weather"}
            )
    
    async def _get_coords_from_city_name(self, city_name: str) -> Optional[Dict]:
        """지역명으로부터 좌표 정보 가져오기"""
        try:
            from services.location_service import LocationService
            location_service = LocationService()
            return await location_service.get_coords_from_city_name(city_name)
        except Exception as e:
            print(f"좌표 변환 오류: {e}")
            return None
    
    async def _get_city_name_from_coords(self, latitude: float, longitude: float) -> Optional[str]:
        """좌표로부터 지역명 가져오기"""
        try:
            from services.location_service import LocationService
            location_service = LocationService()
            return await location_service.get_city_name_from_coords(latitude, longitude)
        except Exception as e:
            print(f"지역명 변환 오류: {e}")
            return None
    
    async def _get_current_weather(self, latitude: float, longitude: float) -> Dict:
        """현재 날씨 정보 가져오기 (기본)"""
        try:
            from services.weather_service import WeatherService
            weather_service = WeatherService()
            return await weather_service.get_current_weather(latitude, longitude)
        except Exception as e:
            print(f"날씨 정보 조회 오류: {e}")
            return {"error": str(e)}

    async def _get_advanced_weather(self, latitude: float, longitude: float) -> Dict:
        """고급 날씨 정보 가져오기 (실황+예보 합성)"""
        try:
            from services.weather_service import WeatherService
            weather_service = WeatherService()
            return await weather_service.get_weather_with_rain_merge(latitude, longitude)
        except Exception as e:
            print(f"고급 날씨 정보 조회 오류: {e}")
            # 기본 날씨 정보로 fallback
            return await self._get_current_weather(latitude, longitude)
    
    def _generate_weather_message(self, location_display_name: str, weather_data: Dict) -> str:
        """날씨 정보 메시지 생성"""
        temp = weather_data.get('temperature')
        sky = weather_data.get('sky_status')
        precip_type = weather_data.get('precipitation_type')
        precip_amount = weather_data.get('precipitation_amount')
        feels_like = weather_data.get('feels_like')
        humidity = weather_data.get('humidity')
        wind_speed = weather_data.get('wind_speed')
        raining_now = weather_data.get('raining_now')
        
        message = f"{location_display_name}의 날씨를 알려드릴게요! ☀️\n\n"
        
        if temp is not None:
            try:
                temp_float = float(temp)
                message += f"🌡️ **기온**: {temp}°C\n"
                
                # 체감온도 표시
                if feels_like is not None:
                    message += f"🌡️ **체감온도**: {feels_like}°C\n"
            except ValueError:
                message += f"🌡️ **기온**: {temp}°C (온도 정보 처리 중 오류 발생)\n"
        
        if sky:
            message += f"☁️ **하늘**: {sky}\n"
        
        if humidity is not None:
            message += f"💧 **습도**: {humidity}%\n"
        
        if wind_speed is not None:
            message += f"💨 **풍속**: {wind_speed}m/s\n"
        
        if precip_type and precip_type != "강수 없음":
            message += f"🌧️ **강수 형태**: {precip_type}\n"
        
        # 강수량이 있고, 0mm가 아닐 때만 표시
        if precip_amount and float(precip_amount) > 0:
            message += f"☔ **시간당 강수량**: {precip_amount}mm\n"
        
        # 비 오는지 여부
        if raining_now:
            message += f"🌧️ **현재 상태**: 비가 오고 있어요!\n"
        
        return message
    

    
    def extract_weather_info_from_message(self, message: str) -> Optional[Dict]:
        """
        날씨 메시지에서 기온 정보 추출
        
        Returns:
            Dict with 'temperature' or None
        """
        import re
        
        try:
            # 기온 추출
            temp_match = re.search(r'(\d+(?:\.\d+)?)°C', message)
            temperature = float(temp_match.group(1)) if temp_match else None
            
            if temperature is not None:
                return {
                    "temperature": temperature
                }
            
        except Exception as e:
            print(f"날씨 정보 추출 오류: {e}")
        
        return None

    async def _enhance_weather_with_clothing(self, weather_message: str, weather_data: Dict, user_gender: str, location_display_name: str = "현재 위치", situations: List[str] = None) -> tuple[str, List[Dict]]:
        """날씨 응답에 실제 상품 추천 추가"""
        try:
            # 날씨 정보에서 기온 추출
            weather_info = self.extract_weather_info_from_message(weather_message)
            
            if weather_info and weather_info.get("temperature") is not None:
                # 날씨 데이터를 더 상세하게 활용
                enhanced_weather_desc = self._create_enhanced_weather_description(weather_data)
                
                # 의류 카테고리 추천 생성 (상황 정보 포함)
                recommended_clothing = await self.recommend_clothing_by_weather(
                    enhanced_weather_desc, 
                    user_gender,
                    weather_data=weather_data,
                    location=location_display_name,
                    situation=", ".join(situations) if situations else None
                )
                
                # CommonSearch를 사용해 실제 상품 검색
                if recommended_clothing and any(recommended_clothing.values()):
                    weather_products = await self._search_weather_products(recommended_clothing)
                    
                    if weather_products:
                        # 추천 메시지에 실제 상품 정보와 추천이유 추가
                        clothing_message = f"\n\n🎯 **오늘 날씨 맞춤 상품**\n"
                        
                        # 각 상품에 대한 추천 이유 매핑
                        recommendations = recommended_clothing.get("recommendations", [])
                        
                        for i, product in enumerate(weather_products[:3], 1):
                            product_name = product.get('상품명', '상품명 없음')
                            brand = product.get('한글브랜드명', '브랜드 없음')
                            price = product.get('원가', 0)
                            
                            clothing_message += f"**{i}. {product_name}**\n"
                            clothing_message += f"   📍 브랜드: {brand}\n"
                            if price:
                                clothing_message += f"   💰 가격: {price:,}원\n"
                            
                            # 해당 상품의 추천 이유 찾기
                            product_reason = ""
                            if recommendations and i <= len(recommendations):
                                rec = recommendations[i-1]
                                reason = rec.get("reason", "")
                                if reason:
                                    product_reason = f"   💡 추천 이유: {reason}\n"
                            
                            if product_reason:
                                clothing_message += product_reason
                            
                            clothing_message += "\n"
                        
                        return weather_message + clothing_message, weather_products[:3]
                    else:
                        # 실제 상품이 없으면 새로운 JSON 구조로 추천 표시
                        recommendations = recommended_clothing.get("recommendations", [])
                        
                        if recommendations:
                            clothing_message = f"\n\n🎯 **오늘 날씨 추천**\n"
                            for i, rec in enumerate(recommendations, 1):
                                item = rec.get("item", "")
                                style = rec.get("style", "")
                                color = rec.get("color", "")
                                reason = rec.get("reason", "")
                                
                                clothing_message += f"**{i}. {item}**\n"
                                if style:
                                    clothing_message += f"   🎨 스타일: {style}\n"
                                if color:
                                    clothing_message += f"   🌈 색상: {color}\n"
                                if reason:
                                    clothing_message += f"   💡 이유: {reason}\n"
                                clothing_message += "\n"
                            
                            return weather_message + clothing_message, []
                        
                        # 기존 구조도 지원 (fallback)
                        clothing_parts = []
                        categories = recommended_clothing.get("categories", [])
                        specific_items = recommended_clothing.get("specific_items", [])
                        
                        if categories:
                            clothing_parts.append(f"카테고리: {', '.join(categories)}")
                        if specific_items:
                            clothing_parts.append(f"추천 아이템: {', '.join(specific_items)}")
                        
                        if clothing_parts:
                            clothing_message = f"\n\n🎯 **오늘 날씨 추천**\n{', '.join(clothing_parts)}을(를) 추천해 드려요!"
                            return weather_message + clothing_message, []
            
            # 의류 추천이 없으면 원본 메시지만 반환
            return weather_message, []
                        
        except Exception as e:
            print(f"날씨 의류 추천 오류: {e}")
            return weather_message, []

    def _create_enhanced_weather_description(self, weather_data: Dict) -> str:
        """날씨 데이터를 종합하여 향상된 날씨 설명 생성"""
        enhanced_parts = []
        
        # 온도 정보 추가
        temp = weather_data.get('temperature')
        feels_like = weather_data.get('feels_like')
        if temp is not None:
            enhanced_parts.append(f"현재 기온 {temp}°C")
            if feels_like is not None and feels_like != temp:
                enhanced_parts.append(f"체감온도 {feels_like}°C")
        
        # 습도 정보 추가
        humidity = weather_data.get('humidity')
        if humidity is not None:
            if humidity >= 70:
                enhanced_parts.append("습도 높음")
            elif humidity <= 30:
                enhanced_parts.append("습도 낮음")
        
        # 바람 정보 추가
        wind_speed = weather_data.get('wind_speed')
        if wind_speed is not None:
            if float(wind_speed) >= 7:
                enhanced_parts.append("바람 강함")
            elif float(wind_speed) >= 3:
                enhanced_parts.append("바람 있음")
        
        # 강수 정보 추가
        raining_now = weather_data.get('raining_now')
        precip_type = weather_data.get('precipitation_type')
        if raining_now or (precip_type and precip_type != "강수 없음"):
            enhanced_parts.append("강수 있음")
        
        return ", ".join(enhanced_parts)

    async def _search_weather_products(self, recommended_clothing: Dict) -> List[Dict]:
        """날씨 기반 추천 의류의 실제 상품 검색 - 의미적으로 연결된 조합 지원"""
        try:
            from services.common_search import CommonSearchModule, SearchQuery
            from data_store import clothing_data
            
            search_module = CommonSearchModule()
            
            # 새로운 JSON 구조에서 추천 데이터 추출
            recommendations = recommended_clothing.get("recommendations", [])
            
            if not recommendations:
                print("추천 데이터가 없습니다.")
                return []
            
            print(f"🔍 WeatherAgent 검색 시작: 추천 {len(recommendations)}개")
            
            all_products = []
            
            # 각 추천 조합별로 검색
            for rec in recommendations:
                item = rec.get("item", "")
                color = rec.get("color", "")
                style = rec.get("style", "")
                
                if not item:
                    continue
                
                print(f"🔍 조합 검색: {item} + {color} + {style}")
                
                # 개별 조합별 검색 쿼리 생성
                search_query = SearchQuery(
                    categories=[item],
                    colors=[color] if color else [],
                    situations=["날씨"],
                    styles=[style] if style else []
                )
                
                # 해당 조합으로 검색
                search_result = search_module.search_products(
                    query=search_query,
                    available_products=clothing_data
                )
                
                if search_result.products:
                    # 각 조합당 1개씩만 추가 (프론트에서 3개 표시하므로)
                    selected_product = search_result.products[0]
                    all_products.append(selected_product)
                    print(f"  ✅ {item} + {color} + {style}: 1개 상품 발견")
                else:
                    print(f"  ⚠️ {item} + {color} + {style}: 검색 결과 없음")
            
            # 중복 제거 (상품코드 기준)
            seen_ids = set()
            unique_products = []
            for product in all_products:
                product_id = product.get("상품코드", "")
                if product_id and product_id not in seen_ids:
                    seen_ids.add(product_id)
                    unique_products.append(product)
            
            print(f"🎯 의미적 조합 검색 완료: 총 {len(unique_products)}개 (중복 제거 후)")
            return unique_products  # 모든 고유 상품 반환 (최대 3개)
            
        except Exception as e:
            print(f"날씨 상품 검색 오류: {e}")
            return []

    def build_context_for_llm(self, weather: Dict, gender: str, 
                            location: str = "현재 위치", situation: str = None,
                            must_prefer: List[str] = None, must_avoid: List[str] = None,
                            explain: bool = False, max_per_category: int = 3) -> Dict:
        """LLM을 위한 날씨 컨텍스트 구성"""
        must_prefer = must_prefer or []
        must_avoid = must_avoid or []

        # 체감온도 계산
        t = weather.get("temperature")
        h = weather.get("humidity")
        fl = weather.get("feels_like")
        if fl is None and t is not None:
            from services.weather_service import feels_like_c
            fl = feels_like_c(t, h)
            if fl is not None:
                weather["feels_like"] = round(fl, 1)


        return {
            "runtime": {
                "datetime": "현재",
                "location": location,
            },
            "user": {
                "gender": gender,
                "situation": situation,
                "must_prefer": must_prefer,
                "must_avoid": must_avoid,
            },
            "weather": {
                "temp_c": round(float(t), 1) if t is not None else None,
                "feels_like_c": weather.get("feels_like"),
                "humidity": int(h) if h is not None else None,
                "wind_ms": round(float(weather.get("wind_speed", 0)), 1) if weather.get("wind_speed") is not None else None,
                "precip_type": weather.get("precipitation_type"),
                "precip_mmph": float(weather.get("precipitation_amount", 0.0) or 0.0),
                "raining_now": bool(weather.get("raining_now", False)),
                "sky_status": weather.get("sky_status")
            },
            "catalog": CATALOG,
            "constraints": {
                "max_per_category": max_per_category,
                "materials_colors_forbidden": True,
                "explain": explain
            }
        }

    def build_system_prompt(self, max_per_category: int = 4) -> str:
         """LLM 시스템 프롬프트 생성 - 의미적으로 연결된 조합 지원"""
         return f"""
[역할]
너는 날씨 기반 의류 추천 어시스턴트다.

[카탈로그]
- 상의: 후드티, 셔츠/블라우스, 긴소매, 반소매, 피케/카라, 니트/스웨터, 슬리브리스
- 바지: 데님팬츠, 트레이닝/조거팬츠, 코튼팬츠, 슈트팬츠/슬랙스, 숏팬츠, 카고팬츠
- 원피스(여성만): 미니원피스, 미디원피스, 맥시원피스
- 스커트(여성만): 미니스커트, 미디스커트, 롱스커트

[색상 옵션]
- 기본색: 빨간색, 파란색, 검은색, 흰색, 회색, 베이지, 갈색, 노란색, 초록색, 분홍색, 보라색, 주황색
- 특수색: 카키, 민트, 네이비, 와인, 올리브

[스타일 옵션]
- 캐주얼, 정장, 스포티, 데이트, 출근, 파티, 운동, 여행, 면접

[규칙]
1) 반드시 위 카탈로그 내 아이템만 추천한다. (카테고리 밖 제안 금지)
2) 소재, 액세서리, 신발 언급 금지.
3) 카테고리별 추천 개수는 1~{max_per_category}개.
4) 성별이 여성일 때만 원피스/스커트 섹션을 포함한다.
5) 비/눈/강풍/습도/체감온도를 종합 반영한다.
   - raining_now=true 또는 precip_type!='강수 없음' → 데님 감점, 조거·코튼 가점, 미니 감점·미디/롱 가점
   - 습도≥70% & 체감≥24℃ → 반소매/슬리브리스/피케, 조거/코튼 가점
   - 바람≥7m/s → 숏팬츠/미니 감점, 긴소매/후드티/미디·롱 가점
6) 상황(situation) 반영:
   - 출근/하객: 셔츠/블라우스, 슬랙스, 미디스커트 가점
   - 야외활동: 트레이닝/조거, 숏팬츠 가점
   - 데이트: (여성) 원피스/미디스커트 가점
   - 면접: 셔츠/블라우스, 슬랙스, 정장 스타일 가점
   - 파티: 원피스, 미니스커트, 화려한 스타일 가점
   - 운동: 트레이닝/조거, 슬리브리스, 편안한 스타일 가점
   - 여행: 편안하고 실용적인 스타일 가점
7) must_avoid은 절대 추천하지 않는다. must_prefer는 있으면 우선 포함한다.
8) 각 아이템마다 의미적으로 연결된 스타일과 색상을 조합하여 추천한다.
9) reason에 색상과 스타일, 날씨를 포함하여 추천 이유를 작성한다.
9) 출력은 설명 없이 **순수 JSON만**. 형식:

{{
  "recommendations": [
    {{
      "item": "후드티",
      "style": "캐주얼",
      "color": "네이비",
      "reason": "따뜻한 봄 날씨에 적합한 캐주얼한 후드티"
    }},
    {{
      "item": "트레이닝/조거팬츠",
      "style": "스포티", 
      "color": "블랙",
      "reason": "편안한 스포티 룩을 위한 조거팬츠"
    }},
    {{
      "item": "코튼팬츠",
      "style": "캐주얼",
      "color": "베이지", 
      "reason": "일상적인 캐주얼 룩에 적합한 코튼팬츠"
    }}
  ]
}}

[입력]
다음 JSON 컨텍스트를 사용해 규칙에 맞는 추천을 반환하라.
""".strip()

    async def recommend_clothing_by_weather(self, weather_description: str, gender: str, 
                                          weather_data: Dict = None, location: str = "현재 위치",
                                          situation: str = None, must_prefer: List[str] = None,
                                          must_avoid: List[str] = None) -> dict:
        """날씨 상황과 성별에 따라 의류를 추천합니다."""
        try:
            # 개선된 프롬프트 사용
            system_prompt = self.build_system_prompt(max_per_category=3)
            
            # 날씨 데이터가 있으면 상세한 컨텍스트 구성
            if weather_data:
                context = self.build_context_for_llm(
                    weather=weather_data,
                    gender=gender,
                    location=location,
                    situation=situation,
                    must_prefer=must_prefer or [],
                    must_avoid=must_avoid or [],
                    explain=False,
                    max_per_category=3
                )
                
                # 컨텍스트를 JSON 형태로 변환하여 프롬프트에 포함
                context_json = json.dumps(context, ensure_ascii=False, indent=2)
                user_prompt = f"다음 컨텍스트를 사용해 규칙에 맞는 추천을 반환하라:\n\n{context_json}"
            else:
                # 날씨 데이터가 없는 경우 기본 컨텍스트
                context = {
                    "weather_description": weather_description,
                    "gender": gender,
                    location: location,
                    "situation": situation
                }
                user_prompt = f"날씨 상황: {weather_description}, 성별: {gender}, 위치: {location}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            raw_llm_response_content = response.choices[0].message.content
            print(f"DEBUG: Raw LLM response content: {raw_llm_response_content}")
            recommended_items = json.loads(raw_llm_response_content)
            print(f"DEBUG: Parsed recommended_items: {recommended_items}")
            return recommended_items
            
        except Exception as e:
            print(f"LLM 의류 추천 요청 오류: {e}")
            # 오류 시 기본값 또는 빈 목록 반환
            return {"상의": [], "하의": []}
    
    def _analyze_weather_request(self, user_input: str) -> Dict:
        """사용자 입력을 분석하여 날씨 관련 정보 추출 (내부 LLM 분석)"""
        system_prompt = """당신은 날씨 관련 요청 분석기입니다.
사용자의 입력을 분석하여 다음 정보를 추출해주세요.

**응답 형식 (JSON):**
{
    "locations": ["추출된 지역명들"],
    "situations": ["추출된 상황들"]
}

**중요 규칙:**
1. 지역명: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 제주, 강남, 홍대 등
2. 상황: 데이트, 출근, 하객, 야외활동, 운동, 여행, 파티, 면접 등
3. 날씨 관련 키워드가 있으면 situations에 "날씨" 추가
4. 지역명이 없으면 빈 배열 반환"""

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
            print(f"날씨 요청 분석 오류: {e}")
            # 오류 시 기본값 반환
            return {"locations": [], "situations": []}
