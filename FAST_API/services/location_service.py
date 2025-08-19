import httpx
import os
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class LocationService:
    """
    Google Maps Geocoding API를 사용하여 지역명을 위도/경도 좌표로 변환하는 서비스
    """
    def __init__(self):
        self.api_key = os.getenv("GOOGLEMAP_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    async def get_coords_from_city_name(self, city_name: str) -> Optional[Dict[str, float]]:
        """
        도시 이름을 받아 위도와 경도를 반환합니다.
        """
        if not self.api_key:
            print("GOOGLEMAP_API_KEY가 .env 파일에 설정되지 않았습니다.")
            return None

        params = {
            "address": city_name,
            "key": self.api_key,
            "language": "ko"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                print(f"'{city_name}'에 대한 위치 정보를 찾을 수 없습니다. (상태: {data.get('status')})")
                return None
            
            location = data["results"][0]["geometry"]["location"]
            lat = location["lat"]
            lon = location["lng"]
            
            print(f"'{city_name}'의 좌표 (Google): 위도={lat}, 경도={lon}")
            return {"latitude": lat, "longitude": lon}

        except httpx.RequestError as e:
            print(f"Google Maps API 요청 오류: {e}")
            return None
        except (KeyError, IndexError, TypeError) as e:
            print(f"Google Maps API 응답 처리 오류: {e}")
            return None

    async def get_city_name_from_coords(self, lat: float, lon: float) -> Optional[str]:
        """
        위도와 경도를 받아 주소/지역명을 반환합니다. (리버스 지오코딩)
        """
        if not self.api_key:
            print("GOOGLEMAP_API_KEY가 .env 파일에 설정되지 않았습니다.")
            return None

        params = {"latlng": f"{lat},{lon}", "key": self.api_key, "language": "ko"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or not data.get("results"):
                print(f"좌표 ({lat}, {lon})에 대한 지역명을 찾을 수 없습니다. (상태: {data.get('status')})")
                return None

            # 주소 구성요소에서 원하는 레벨의 지역명 찾기 (예: OO시 OO구)
            address_components = data["results"][0].get("address_components", [])
            level1 = ""
            level2 = ""
            for comp in address_components:
                types = comp.get("types", [])
                if "administrative_area_level_1" in types:
                    level1 = comp.get("long_name", "")
                if "locality" in types or "sublocality_level_1" in types:
                    level2 = comp.get("long_name", "")
                if level1 and level2:
                    break
            
            city_name = f"{level1} {level2}".strip()
            if not city_name:
                # 실패 시 전체 주소 사용
                city_name = data["results"][0].get("formatted_address", "알 수 없는 위치")

            print(f"좌표 ({lat}, {lon})의 지역명 (Google): {city_name}")
            return city_name

        except Exception as e:
            print(f"Google Maps API (리버스 지오코딩) 오류: {e}")
            return None