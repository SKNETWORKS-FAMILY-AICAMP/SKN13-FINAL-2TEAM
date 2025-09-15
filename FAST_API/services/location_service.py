import httpx
import os
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

<<<<<<< Updated upstream
# 기본 위치 설정 (서울 금천구)
DEFAULT_LAT, DEFAULT_LON = 37.455, 126.893
LOCATION_NAME = "서울 금천구"
=======
>>>>>>> Stashed changes

class LocationService:
    """
    Google Maps Geocoding API와 OpenStreetMap Nominatim API를 사용하여 
    지역명을 위도/경도 좌표로 변환하는 서비스
    """
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLEMAP_API_KEY")
        self.google_base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.nominatim_base_url = "https://nominatim.openstreetmap.org"

    async def get_coords_from_city_name(self, city_name: str, use_google: bool = True) -> Optional[Dict[str, float]]:
        """
        도시 이름을 받아 위도와 경도를 반환합니다.
        
        Args:
            city_name: 도시 이름
            use_google: True면 Google Maps API, False면 OpenStreetMap API 사용
        """
        if use_google and self.google_api_key:
            return await self._get_coords_from_google(city_name)
        else:
            return await self._get_coords_from_nominatim(city_name)

    async def get_city_name_from_coords(self, lat: float, lon: float, use_google: bool = True) -> Optional[str]:
        """
        위도와 경도를 받아 주소/지역명을 반환합니다. (리버스 지오코딩)
        
        Args:
            lat: 위도
            lon: 경도
            use_google: True면 Google Maps API, False면 OpenStreetMap API 사용
        """
        if use_google and self.google_api_key:
            return await self._get_city_name_from_google(lat, lon)
        else:
            return await self._get_city_name_from_nominatim(lat, lon)

    async def _get_coords_from_google(self, city_name: str) -> Optional[Dict[str, float]]:
        """Google Maps API를 사용한 좌표 조회"""
        if not self.google_api_key:
            print("GOOGLEMAP_API_KEY가 .env 파일에 설정되지 않았습니다.")
            return None

        params = {
            "address": city_name,
            "key": self.google_api_key,
            "language": "ko"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.google_base_url, params=params)
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

    async def _get_coords_from_nominatim(self, city_name: str) -> Optional[Dict[str, float]]:
        """OpenStreetMap Nominatim API를 사용한 좌표 조회"""
        params = {
            "q": city_name,
            "format": "json",
            "limit": 1,
            "accept-language": "ko"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.nominatim_base_url}/search", params=params)
                response.raise_for_status()
                
            data = response.json()
            
            if not data:
                print(f"'{city_name}'에 대한 위치 정보를 찾을 수 없습니다. (Nominatim)")
                return None
            
            location = data[0]
            lat = float(location["lat"])
            lon = float(location["lon"])
            
            print(f"'{city_name}'의 좌표 (Nominatim): 위도={lat}, 경도={lon}")
            return {"latitude": lat, "longitude": lon}

        except httpx.RequestError as e:
            print(f"Nominatim API 요청 오류: {e}")
            return None
        except (KeyError, IndexError, TypeError, ValueError) as e:
            print(f"Nominatim API 응답 처리 오류: {e}")
            return None

    async def _get_city_name_from_google(self, lat: float, lon: float) -> Optional[str]:
        """Google Maps API를 사용한 리버스 지오코딩"""
        if not self.google_api_key:
            print("GOOGLEMAP_API_KEY가 .env 파일에 설정되지 않았습니다.")
            return None

        params = {"latlng": f"{lat},{lon}", "key": self.google_api_key, "language": "ko"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.google_base_url, params=params)
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

    async def _get_city_name_from_nominatim(self, lat: float, lon: float) -> Optional[str]:
        """OpenStreetMap Nominatim API를 사용한 리버스 지오코딩"""
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "accept-language": "ko"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.nominatim_base_url}/reverse", params=params)
                response.raise_for_status()
                
            data = response.json()
            
            if not data.get("display_name"):
                print(f"좌표 ({lat}, {lon})에 대한 지역명을 찾을 수 없습니다. (Nominatim)")
                return None
            
            # 주소에서 시/구 레벨 추출
            address_parts = data["display_name"].split(", ")
            if len(address_parts) >= 3:
                # 보통 "도로명, 구, 시, 도, 국가" 순서
                city_name = f"{address_parts[-3]} {address_parts[-4]}" if len(address_parts) >= 4 else address_parts[-3]
            else:
                city_name = data["display_name"]
            
            print(f"좌표 ({lat}, {lon})의 지역명 (Nominatim): {city_name}")
            return city_name

        except httpx.RequestError as e:
            print(f"Nominatim API 요청 오류: {e}")
            return None
        except (KeyError, IndexError, TypeError) as e:
            print(f"Nominatim API 응답 처리 오류: {e}")
            return None

<<<<<<< Updated upstream
    def get_default_location(self) -> Dict[str, float]:
        """기본 위치 반환"""
        return {"latitude": DEFAULT_LAT, "longitude": DEFAULT_LON}

    def get_default_location_name(self) -> str:
        """기본 위치명 반환"""
        return LOCATION_NAME
=======
    
    async def get_current_location_from_ip(self) -> Optional[Dict[str, float]]:
        """IP 기반으로 현재 위치의 좌표를 가져옵니다."""
        try:
            async with httpx.AsyncClient() as client:
                # ipapi.co 서비스 사용 (무료, 1000회/월)
                response = await client.get("http://ipapi.co/json/", timeout=5.0)
                response.raise_for_status()
                
                data = response.json()
                
                if "latitude" in data and "longitude" in data:
                    lat = float(data["latitude"])
                    lon = float(data["longitude"])
                    
                    print(f"IP 기반 현재 위치: 위도={lat}, 경도={lon}")
                    return {"latitude": lat, "longitude": lon}
                else:
                    print("IP 기반 위치 정보를 가져올 수 없습니다.")
                    return None
                    
        except Exception as e:
            print(f"IP 기반 위치 조회 오류: {e}")
            return None
>>>>>>> Stashed changes
