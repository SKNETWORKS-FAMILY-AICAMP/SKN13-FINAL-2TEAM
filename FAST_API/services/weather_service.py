import httpx
import os
from typing import Dict, Optional, Any
from dotenv import load_dotenv
import math
from datetime import datetime, timedelta
import ssl

load_dotenv()

def convert_gps_to_grid(lat: float, lon: float) -> Dict[str, int]:
    """
    기상청 API가 사용하는 LCC 격자 좌표계로 변환하는 함수.
    """
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136
    DEGRAD = math.pi / 180.0

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (math.pow(sf, sn) * math.cos(slat1)) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = (re * sf) / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = (re * sf) / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi: theta -= 2.0 * math.pi
    if theta < -math.pi: theta += 2.0 * math.pi
    theta *= sn

    x = math.floor(ra * math.sin(theta) + XO + 0.5)
    y = math.floor(ro - ra * math.cos(theta) + YO + 0.5)

    return {"x": int(x), "y": int(y)}

class WeatherService:
    """
    기상청 초단기 실황 API와 연동하여 현재 날씨 정보를 가져오는 서비스
    """
    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY")
        self.base_url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"

    async def get_current_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        주어진 위도와 경도를 기반으로 현재 날씨 실황을 조회합니다.
        """
        if not self.api_key:
            print("WEATHER_API_KEY가 .env 파일에 설정되지 않았습니다.")
            return {"error": "날씨 API 키가 설정되지 않았습니다."}

        grid = convert_gps_to_grid(latitude, longitude)
        now = datetime.now()
        
        # API는 매시 30분에 생성되어 40분~45분 사이에 제공됩니다.
        # 현재 시간이 45분 미만이면, 한 시간 전 데이터를 요청해야 안정적입니다.
        if now.minute < 45:
            base_datetime = now - timedelta(hours=1)
        else:
            base_datetime = now

        base_date = base_datetime.strftime("%Y%m%d")
        base_time = base_datetime.strftime("%H00")

        params = {
            "serviceKey": self.api_key,
            "pageNo": 1,
            "numOfRows": 10,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": grid["x"],
            "ny": grid["y"],
        }

        ssl_context = ssl.create_default_context()
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')

        try:
            async with httpx.AsyncClient(verify=ssl_context) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
            data = response.json()
            
            if data.get("response", {}).get("header", {}).get("resultCode") != "00":
                error_msg = data.get("response", {}).get("header", {}).get("resultMsg", "Unknown error")
                print(f"날씨 API 오류: {error_msg}")
                return {"error": f"날씨 API 오류: {error_msg}"}

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            weather_info = {}
            for item in items:
                category = item.get("category")
                value = item.get("obsrValue") # 실황 API는 obsrValue 사용
                if category == "T1H": # 1시간 내 기온
                    weather_info["temperature"] = value
                elif category == "SKY": # 하늘 상태
                    sky_map = {"1": "맑음", "3": "구름 많음", "4": "흐림"}
                    weather_info["sky_status"] = sky_map.get(value, "알 수 없음")
                elif category == "PTY": # 강수 형태
                    pty_map = {"0": "강수 없음", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림"}
                    weather_info["precipitation_type"] = pty_map.get(value, "알 수 없음")
                elif category == "RN1": # 1시간 강수량
                    weather_info["precipitation_amount"] = value
            
            if not weather_info:
                 return {"error": "파싱할 날씨 정보가 없습니다."}

            return weather_info

        except httpx.RequestError as e:
            print(f"날씨 API 요청 오류: {e}")
            return {"error": "날씨 정보를 가져오는 데 실패했습니다."}
        except Exception as e:
            print(f"날씨 정보 처리 중 오류: {e}")
            return {"error": "날씨 정보를 처리하는 중 오류가 발생했습니다."}