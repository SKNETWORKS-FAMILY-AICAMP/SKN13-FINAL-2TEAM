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

def feels_like_c(temp_c: float, humidity: int) -> float:
    """간단 Heat Index 근사. 27℃↑ & 습도↑에서만 소폭 가산."""
    if temp_c is None: 
        return None
    if temp_c < 27 or (humidity is not None and humidity < 40):
        return temp_c
    h = 50 if humidity is None else humidity
    return temp_c + 0.01 * (h - 40)  # ~0~1.5℃ 가산

def describe_weather_safe(weather: Dict) -> str:
    """모순 표현 방지(우선순위: 강수>바람>습도), 안전한 문장 생성"""
    t = float(weather.get("temperature")) if weather.get("temperature") is not None else None
    h = int(weather.get("humidity", 50))
    wind = float(weather.get("wind_speed", 0))
    ptype = weather.get("precipitation_type", "강수 없음")

    fl = round(feels_like_c(t, h), 1) if t is not None else None

    # 기본 온도대
    if fl is None:
        base = "현재 날씨"
    elif fl >= 35: base = "폭염, 숨 막히는 더위"
    elif fl >= 30: base = "매우 더운 날씨"
    elif fl >= 28: base = "더운 여름 날씨"
    elif fl >= 25: base = "따뜻한 초여름 날씨"
    elif fl >= 20: base = "온화한 날씨"
    elif fl >= 15: base = "선선한 날씨"
    elif fl >= 10: base = "쌀쌀한 날씨"
    elif fl >= 5:  base = "차가운 날씨"
    else:          base = "매우 추운 날씨"

    # 보정 우선순위 적용
    if ptype not in ("강수 없음", None):
        desc = f"{'눈 내리는' if '눈' in ptype else '비 오는'} {base}"
    elif wind >= 7:
        desc = f"바람이 강한 {base}"
    elif h >= 70 and (fl is not None and fl >= 24):
        desc = f"후덥지근한 {base}"
    elif h <= 35 and (fl is not None and fl <= 15):
        desc = f"건조한 {base}"
    else:
        desc = base

    if t is None or fl is None:
        return f"{desc} (습도 {h}%, 풍속 {wind:.1f}m/s, 강수: {ptype})"
    return f"{desc} (현재 {t:.1f}℃, 체감 {fl:.1f}℃, 습도 {h}%, 풍속 {wind:.1f}m/s, 강수: {ptype})"

class WeatherService:
    """
    기상청 초단기 실황 API와 연동하여 현재 날씨 정보를 가져오는 서비스
    """
    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY")
        self.base_url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
        self.vilage_base = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"

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
                    weather_info["temperature"] = float(value)
                elif category == "REH": # 습도
                    weather_info["humidity"] = int(value)
                elif category == "WSD": # 풍속
                    weather_info["wind_speed"] = float(value)
                elif category == "SKY": # 하늘 상태
                    sky_map = {"1": "맑음", "3": "구름 많음", "4": "흐림"}
                    weather_info["sky_status"] = sky_map.get(value, "알 수 없음")
                elif category == "PTY": # 강수 형태
                    pty_map = {"0": "강수 없음", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림"}
                    weather_info["precipitation_type"] = pty_map.get(value, "알 수 없음")
                elif category == "RN1": # 1시간 강수량
                    weather_info["precipitation_amount"] = 0.0 if value == "강수없음" else float(value)
            
            if not weather_info:
                 return {"error": "파싱할 날씨 정보가 없습니다."}

            # 체감온도 계산
            if weather_info.get("temperature") is not None:
                weather_info["feels_like"] = feels_like_c(
                    weather_info["temperature"], 
                    weather_info.get("humidity")
                )
                
                # 날씨 설명 생성 (불필요한 날씨 상황 설명 제거)
                # weather_info["weather_description"] = describe_weather_safe(weather_info)

            return weather_info

        except httpx.RequestError as e:
            print(f"날씨 API 요청 오류: {e}")
            return {"error": "날씨 정보를 가져오는 데 실패했습니다."}
        except Exception as e:
            print(f"날씨 정보 처리 중 오류: {e}")
            return {"error": "날씨 정보를 처리하는 중 오류가 발생했습니다."}

    def _kma_base_time_for_ncst(self, now: datetime) -> datetime:
        """실황: 정시 기준 + 약 40분 이후 안정"""
        return (now - timedelta(hours=1)) if now.minute < 40 else now

    def _kma_base_time_for_fcst(self, now: datetime) -> datetime:
        """
        초단기 예보(getUltraSrtFcst): base_time은 HH00 또는 HH30만 유효.
        발표 직후 공백을 피하려고 약간 과거 슬롯을 선택.
        """
        minute_slot = 30 if now.minute >= 30 else 0
        base = now.replace(minute=minute_slot, second=0, microsecond=0)
        if (minute_slot == 30 and now.minute < 35) or (minute_slot == 0 and now.minute < 5):
            base -= timedelta(minutes=30)
        return base

    async def _fetch_ultra_ncst(self, nx: int, ny: int, base_dt: datetime) -> Dict:
        """초단기 실황 데이터 조회"""
        params = {
            "serviceKey": self.api_key,
            "pageNo": 1, "numOfRows": 100,
            "dataType": "JSON",
            "base_date": base_dt.strftime("%Y%m%d"),
            "base_time": base_dt.strftime("%H00"),
            "nx": nx, "ny": ny,
        }
        url = f"{self.vilage_base}/getUltraSrtNcst"
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        
        async with httpx.AsyncClient(verify=ssl_ctx, timeout=12.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def _fetch_ultra_fcst(self, nx: int, ny: int, base_dt: datetime) -> Dict:
        """초단기 예보 데이터 조회"""
        params = {
            "serviceKey": self.api_key,
            "pageNo": 1, "numOfRows": 1000,
            "dataType": "JSON",
            "base_date": base_dt.strftime("%Y%m%d"),
            "base_time": base_dt.strftime("%H%M"),  # HH00 또는 HH30
            "nx": nx, "ny": ny,
        }
        url = f"{self.vilage_base}/getUltraSrtFcst"
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        
        async with httpx.AsyncClient(verify=ssl_ctx, timeout=12.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                # JSON이 아니면(대개 XML/HTML 에러) 디버깅
                text = r.text[:400]
                raise RuntimeError(
                    f"FCST JSON parse failed. base_time={params['base_time']}, "
                    f"status={r.status_code}, body[:400]={text!r}"
                )

    def _parse_ncst(self, items: list) -> Dict:
        """실황 데이터 파싱"""
        sky_map = {"1": "맑음", "3": "구름 많음", "4": "흐림"}
        pty_map = {"0":"강수 없음","1":"비","2":"비/눈","3":"눈","5":"빗방울","6":"빗방울/눈날림","7":"눈날림"}
        out = {}
        for it in items:
            cat, val = it.get("category"), it.get("obsrValue")
            if cat == "T1H": out["temperature"] = float(val)
            elif cat == "REH": out["humidity"] = int(val)
            elif cat == "WSD": out["wind_speed"] = float(val)
            elif cat == "RN1": out["precipitation_amount"] = 0.0 if val == "강수없음" else float(val)
            elif cat == "PTY": out["precipitation_type"] = pty_map.get(val, "강수 없음")
            elif cat == "SKY": out["sky_status"] = sky_map.get(val, None)
        return out

    def _raining_from_ncst(self, ncst: Dict) -> bool:
        """실황에서 비 오는지 확인"""
        ptype = ncst.get("precipitation_type")
        rn1 = float(ncst.get("precipitation_amount", 0.0) or 0.0)
        return (ptype is not None and ptype != "강수 없음") or (rn1 > 0)

    def _raining_from_fcst(self, items: list, now: datetime) -> bool:
        """예보에서 비 오는지 확인"""
        # 지금 기준 -10분 ~ +30분 창에서 PTY/PCP 확인
        window_start = (now - timedelta(minutes=10)).strftime("%H%M")
        window_end   = (now + timedelta(minutes=30)).strftime("%H%M")
        
        def in_window(fcst_time: str) -> bool:
            return window_start <= fcst_time <= window_end
            
        pty_is_rain = False
        pcp_is_rain = False
        for it in items:
            cat = it.get("category")
            fcst_time = it.get("fcstTime")
            if not fcst_time or not in_window(fcst_time):
                continue
            if cat == "PTY" and it.get("fcstValue") not in ("0", "None", None):
                pty_is_rain = pty_is_rain or (it["fcstValue"] != "0")
            if cat == "PCP":
                val = it.get("fcstValue")
                if val and val != "강수없음":
                    pcp_is_rain = True
        return pty_is_rain or pcp_is_rain

    async def get_weather_with_rain_merge(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """실황+예보 합성으로 raining_now 강화 + 기본 항목 반환"""
        if not self.api_key:
            raise ValueError("WEATHER_API_KEY not found in .env")

        grid = convert_gps_to_grid(latitude, longitude)
        now = datetime.now()
        base_ncst = self._kma_base_time_for_ncst(now)
        base_fcst = self._kma_base_time_for_fcst(now)

        ncst_json = await self._fetch_ultra_ncst(grid["x"], grid["y"], base_ncst)
        fcst_json = await self._fetch_ultra_fcst(grid["x"], grid["y"], base_fcst)

        ncst_items = ncst_json.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        fcst_items = fcst_json.get("response", {}).get("body", {}).get("items", {}).get("item", [])

        ncst_parsed = self._parse_ncst(ncst_items)
        raining = self._raining_from_ncst(ncst_parsed) or self._raining_from_fcst(fcst_items, now)

        if raining and ncst_parsed.get("precipitation_type", "강수 없음") == "강수 없음":
            ncst_parsed["precipitation_type"] = "비"

        ncst_parsed["raining_now"] = bool(raining)
        
        # 체감온도 계산
        if ncst_parsed.get("temperature") is not None:
            ncst_parsed["feels_like"] = feels_like_c(
                ncst_parsed["temperature"], 
                ncst_parsed.get("humidity")
            )
            
            # 날씨 설명 생성
            # 날씨 설명 생성 (불필요한 날씨 상황 설명 제거)
        # ncst_parsed["weather_description"] = describe_weather_safe(ncst_parsed)

        return ncst_parsed