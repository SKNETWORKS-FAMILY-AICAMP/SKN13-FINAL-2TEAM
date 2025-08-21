"""
Weather Intent Agent
날씨 관련 요청을 처리하는 에이전트
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

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
                                    longitude: Optional[float] = None) -> WeatherAgentResult:
        """
        날씨 요청 처리
        
        Args:
            user_input: 사용자 입력
            extracted_info: 추출된 정보 (지역명 등)
            latitude: 위도
            longitude: 경도
        
        Returns:
            WeatherAgentResult: 날씨 정보 결과
        """
        print(f"=== Weather Agent 시작 ===")
        print(f"사용자 입력: {user_input}")
        print(f"추출된 정보: {extracted_info}")
        
        try:
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
            
            # 날씨 정보 조회
            weather_data = await self._get_current_weather(coords["latitude"], coords["longitude"])
            
            if "error" in weather_data:
                return WeatherAgentResult(
                    success=False,
                    message=f"죄송합니다. 날씨 정보를 가져오는 데 실패했습니다. ({weather_data['error']})",
                    products=[],
                    metadata={"error": "weather_api_failed", "agent_type": "weather"}
                )
            
            # 날씨 메시지 생성
            message = self._generate_weather_message(location_display_name, weather_data)
            
            return WeatherAgentResult(
                success=True,
                message=message,
                products=[],
                metadata={
                    "weather_data": weather_data,
                    "location": location_display_name,
                    "agent_type": "weather"
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
        """현재 날씨 정보 가져오기"""
        try:
            from services.weather_service import WeatherService
            weather_service = WeatherService()
            return await weather_service.get_current_weather(latitude, longitude)
        except Exception as e:
            print(f"날씨 정보 조회 오류: {e}")
            return {"error": str(e)}
    
    def _generate_weather_message(self, location_display_name: str, weather_data: Dict) -> str:
        """날씨 정보 메시지 생성"""
        temp = weather_data.get('temperature')
        sky = weather_data.get('sky_status')
        precip_type = weather_data.get('precipitation_type')
        precip_amount = weather_data.get('precipitation_amount')
        
        message = f"{location_display_name}의 날씨를 알려드릴게요! ☀️\n\n"
        
        if temp is not None:
            try:
                temp_float = float(temp)
                message += f"🌡️ **기온**: {temp}°C\n"
                # 기온에 따른 날씨 상황 설명 추가
                weather_description = self._get_weather_description(temp_float)
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
        
        return message
    
    def _get_weather_description(self, temperature: float) -> str:
        """기온에 따른 날씨 상황 설명"""
        if temperature >= 35:
            return "폭염, 숨 막히는 더위"
        elif temperature >= 30:
            return "한여름, 매우 더운 날씨"
        elif temperature >= 28:
            return "본격적인 여름 날씨"
        elif temperature >= 25:
            return "초여름 날씨"
        elif temperature >= 20:
            return "따뜻한 봄 날씨"
        elif temperature >= 15:
            return "선선한 가을 날씨"
        elif temperature >= 10:
            return "쌀쌀한 가을 날씨"
        elif temperature >= 5:
            return "쌀쌀한 초겨울 날씨"
        else:
            return "추운 겨울 날씨"
    
    def extract_weather_info_from_message(self, message: str) -> Optional[Dict]:
        """
        날씨 메시지에서 기온과 날씨 상황 정보 추출
        
        Returns:
            Dict with 'temperature' and 'weather_description' or None
        """
        import re
        
        try:
            # 기온 추출
            temp_match = re.search(r'(\d+(?:\.\d+)?)°C', message)
            temperature = float(temp_match.group(1)) if temp_match else None
            
            # 날씨 상황 추출
            weather_match = re.search(r'날씨 상황\*\*: (.+)', message)
            weather_description = weather_match.group(1).strip() if weather_match else None
            
            if temperature is not None and weather_description:
                return {
                    "temperature": temperature,
                    "weather_description": weather_description
                }
            
        except Exception as e:
            print(f"날씨 정보 추출 오류: {e}")
        
        return None
