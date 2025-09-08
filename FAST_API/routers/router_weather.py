from fastapi import APIRouter
from services.weather_service import WeatherService

router = APIRouter()

@router.get("/weather")
async def get_weather():
    weather_service = WeatherService()
    return await weather_service.get_weather()
