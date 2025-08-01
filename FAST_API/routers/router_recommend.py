from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import random
import re
import numpy as np
from openai import OpenAI
import os
from typing import List, Dict
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# OpenAI API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")
client = OpenAI(api_key=OPENAI_API_KEY)

# 전역 변수로 데이터 저장
clothing_data = []

def initialize_data():
    """애플리케이션 시작 시 데이터 초기화"""
    load_data()

def clean_nan_values(obj):
    """NaN 값을 None으로 변환하는 함수"""
    if isinstance(obj, dict):
        return {key: clean_nan_values(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif pd.isna(obj) or (isinstance(obj, float) and np.isnan(obj)):
        return None
    else:
        return obj

def load_data():
    """CSV 파일에서 데이터를 로드하는 함수"""
    global clothing_data
    try:
        # CSV 파일 읽기
        df = pd.read_csv("products.csv")
        
        # NaN 값을 None으로 변환
        df = df.replace({np.nan: None})
        
        # 이미지 URL 정리 함수
        def fix_image_url(url):
            if pd.isna(url) or url is None:
                return ""
            url = str(url).strip()
            
            # 이미 올바른 경우
            if url.startswith("https://"):
                return url
            
            # 불완전한 시작 형태면 강제로 접두사 붙임
            if url.startswith("//"):
                return f"https:{url}"
            
            return url

        # 이미지 URL 정리 적용
        if "대표이미지URL" in df.columns:
            df["대표이미지URL"] = df["대표이미지URL"].apply(fix_image_url)
        
        # 데이터프레임을 딕셔너리 리스트로 변환
        raw_data = df.to_dict("records")
        
        # 필드명 매핑하여 새로운 형태로 변환
        clothing_data = []
        for item in raw_data:
            # NaN 값 정리
            item = clean_nan_values(item)
            
            mapped_item = {
                "상품명": item.get("상품명", "") or "",
                "브랜드": item.get("브랜드", "") or "",
                "소재": item.get("소재", "") or "",
                "치수정보": item.get("치수정보", "") or "",
                "색상옵션": item.get("색상옵션", "") or "",
                "사이즈옵션": item.get("사이즈옵션", "") or "",
                "가격": item.get("가격", "") or "",
                "세탁법": item.get("세탁법", "") or "",
                "사진": item.get("대표이미지URL", "") or "",
                "카테고리": "의류",  # 기본값
                "평점": 0.0,
                "리뷰수": 0
            }
            clothing_data.append(mapped_item)
        
        print(f"데이터 로드 완료: {len(clothing_data)}개 상품")
        
    except Exception as e:
        print(f"데이터 로드 오류: {e}")
        clothing_data = []

async def analyze_user_input_with_openai(user_input: str) -> Dict:
    """OpenAI API를 사용하여 사용자 입력을 분석하고 검색 키워드를 추출"""
    try:
        # 시스템 프롬프트 설정 - 상황별 추천에 특화
        system_prompt = """
당신은 패션 추천 시스템의 분석 전문가입니다. 사용자의 입력을 분석하여 의류 검색에 필요한 키워드들을 추출해주세요.

특히 다음 상황별 키워드들을 중점적으로 분석해주세요:
- 데이트: 로맨틱, 예쁜, 우아한, 세련된, 여성스러운, 남성스러운
- 비즈니스/회사: 정장, 깔끔한, 전문적인, 신뢰감, 포멀
- 운동/스포츠: 편안한, 기능적인, 활동적인, 스포티
- 파티/이벤트: 화려한, 고급스러운, 특별한, 눈에 띄는
- 여행: 실용적인, 편리한, 가벼운, 다재다능한
- 일상/캐주얼: 편한, 간단한, 실용적인, 편안한

다음 형식으로 JSON 응답을 제공해주세요:
{
    "season": "여름/겨울/봄/가을/상관없음",
    "style": "캐주얼/정장/스포츠/로맨틱/고급/편안함/상관없음",
    "category": "상의/하의/아우터/신발/가방/액세서리/상관없음",
    "material": "면/린넨/니트/데님/가죽/상관없음",
    "color": "검정/흰색/파랑/빨강/상관없음",
    "occasion": "일상/데이트/비즈니스/운동/파티/여행/상관없음",
    "keywords": ["키워드1", "키워드2", "키워드3"],
    "situation_keywords": ["상황별키워드1", "상황별키워드2"]
}
"""

        # OpenAI API 호출
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"사용자 입력: {user_input}"}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        # 응답 파싱
        analysis_text = response.choices[0].message.content.strip()
        
        # JSON 파싱 시도
        try:
            analysis = json.loads(analysis_text)
            return analysis
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 기본 키워드 추출
            return extract_basic_keywords(user_input)
            
    except Exception as e:
        print(f"OpenAI API 오류: {e}")
        # API 오류 시 기본 키워드 추출
        return extract_basic_keywords(user_input)

def extract_basic_keywords(user_input: str) -> Dict:
    """기본 키워드 추출 (OpenAI API 실패 시 사용)"""
    user_input_lower = user_input.lower()
    
    # 계절 키워드
    season_keywords = {
        "여름": ["여름", "시원한", "가벼운", "린넨", "면", "반팔", "민소매"],
        "겨울": ["겨울", "따뜻한", "패딩", "코트", "니트", "목도리", "긴팔"],
        "봄": ["봄", "가벼운", "자켓", "긴소매"],
        "가을": ["가을", "자켓", "코트", "긴소매"]
    }
    
    # 스타일 키워드
    style_keywords = {
        "캐주얼": ["캐주얼", "편한", "일상"],
        "정장": ["정장", "비즈니스", "수트", "면접"],
        "스포츠": ["운동", "스포츠", "편한", "트레이닝"],
        "로맨틱": ["데이트", "로맨틱", "예쁜"]
    }
    
    # 색상 키워드
    color_keywords = {
        "빨강": ["빨간", "빨강", "레드", "red", "빨간색", "빨강색"],
        "파랑": ["파란", "파랑", "블루", "blue", "파란색", "파랑색"],
        "검정": ["검은", "검정", "블랙", "black", "검은색", "검정색"],
        "흰색": ["흰", "흰색", "화이트", "white", "흰색"],
        "노랑": ["노란", "노랑", "옐로우", "yellow", "노란색", "노랑색"],
        "초록": ["초록", "그린", "green", "초록색"],
        "보라": ["보라", "퍼플", "purple", "보라색"],
        "주황": ["주황", "오렌지", "orange", "주황색"],
        "분홍": ["분홍", "핑크", "pink", "분홍색"],
        "회색": ["회색", "그레이", "gray", "grey", "회색"],
        "갈색": ["갈색", "브라운", "brown", "갈색"],
        "베이지": ["베이지", "beige", "베이지색"]
    }
    
    # 키워드 매칭
    detected_season = "상관없음"
    detected_style = "상관없음"
    detected_category = "상관없음"
    detected_color = "상관없음"
    keywords = []
    
    # 계절 매칭
    for season, words in season_keywords.items():
        if any(word in user_input_lower for word in words):
            detected_season = season
            keywords.extend(words)
    
    # 스타일 매칭
    for style, words in style_keywords.items():
        if any(word in user_input_lower for word in words):
            detected_style = style
            keywords.extend(words)
    
    # 색상 매칭
    for color, words in color_keywords.items():
        if any(word in user_input_lower for word in words):
            detected_color = color
            keywords.extend(words)
    
    return {
        "season": detected_season,
        "style": detected_style,
        "category": detected_category,
        "color": detected_color,
        "material": "상관없음",
        "occasion": "상관없음",
        "keywords": list(set(keywords)),  # 중복 제거
        "situation_keywords": []
    }

def filter_products_by_analysis(analysis: Dict, products: List[Dict]) -> List[Dict]:
    """분석 결과를 바탕으로 상품 필터링"""
    filtered_products = []
    
    for product in products:
        score = 0
        product_text = f"{product.get('상품명', '')} {product.get('브랜드', '')} {product.get('소재', '')} {product.get('색상옵션', '')}".lower()
        
        # 색상 매칭
        if analysis.get("color") != "상관없음":
            color_keywords = {
                "빨강": ["빨간", "빨강", "레드", "red", "빨간색", "빨강색"],
                "파랑": ["파란", "파랑", "블루", "blue", "파란색", "파랑색"],
                "검정": ["검은", "검정", "블랙", "black", "검은색", "검정색"],
                "흰색": ["흰", "흰색", "화이트", "white", "흰색"],
                "노랑": ["노란", "노랑", "옐로우", "yellow", "노란색", "노랑색"],
                "초록": ["초록", "그린", "green", "초록색"],
                "보라": ["보라", "퍼플", "purple", "보라색"],
                "주황": ["주황", "오렌지", "orange", "주황색"],
                "분홍": ["분홍", "핑크", "pink", "분홍색"],
                "회색": ["회색", "그레이", "gray", "grey", "회색"],
                "갈색": ["갈색", "브라운", "brown", "갈색"],
                "베이지": ["베이지", "beige", "베이지색"]
            }
            if any(keyword in product_text for keyword in color_keywords.get(analysis["color"], [])):
                score += 5
        
        # 기본 키워드 매칭
        for keyword in analysis.get("keywords", []):
            if keyword in product_text:
                score += 1
        
        # 점수가 1점 이상인 상품만 포함
        if score > 0:
            product["match_score"] = score
            filtered_products.append(product)
    
    # 점수순으로 정렬
    filtered_products.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    return filtered_products

async def get_smart_recommendations(user_input: str) -> List[Dict]:
    """OpenAI API를 사용한 스마트 추천"""
    global clothing_data
    
    # 데이터가 없으면 로드 시도
    if not clothing_data:
        load_data()
    
    if not clothing_data:
        return []
    
    # OpenAI API로 사용자 입력 분석
    analysis = await analyze_user_input_with_openai(user_input)
    print(f"분석 결과: {analysis}")
    
    # 분석 결과로 상품 필터링
    filtered_products = filter_products_by_analysis(analysis, clothing_data)
    
    if filtered_products:
        # 상위 2개 상품 반환
        return filtered_products[:2]
    else:
        # 매칭되는 상품이 없으면 랜덤 추천
        return random.sample(clothing_data, 2)

@router.get("/", response_class=HTMLResponse)
async def recommend(request: Request):
    # 페이지 로드 시 데이터 로드
    if not clothing_data:
        load_data()
    return templates.TemplateResponse("recommend/recommend.html", {"request": request})

@router.post("/chat", response_class=JSONResponse)
async def chat_recommend(user_input: str = Form(...)):
    """챗봇 추천 API"""
    try:
        # 데이터가 없으면 로드
        if not clothing_data:
            load_data()
        
        # 데이터가 여전히 없으면 오류
        if not clothing_data:
            return {
                "success": False,
                "response": "데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                "recommendations": []
            }
        
        # OpenAI API를 사용한 스마트 추천
        recommendations = await get_smart_recommendations(user_input)
        
        # LLM 기반 상황별 응답 메시지 생성
        analysis = await analyze_user_input_with_openai(user_input)
        
        if analysis.get("occasion") == "데이트":
            response_msg = "데이트에 어울리는 로맨틱하고 우아한 옷들을 추천해드릴게요! 💕"
        elif analysis.get("occasion") == "비즈니스":
            response_msg = "비즈니스에 어울리는 전문적이고 신뢰감 있는 옷들을 추천해드릴게요! 👔"
        elif analysis.get("occasion") == "운동":
            response_msg = "운동할 때 편하게 입을 수 있는 기능적인 스포츠웨어를 추천해드릴게요! 💪"
        elif analysis.get("occasion") == "파티":
            response_msg = "파티에 어울리는 화려하고 고급스러운 옷들을 추천해드릴게요! 🎉"
        elif analysis.get("occasion") == "여행":
            response_msg = "여행에 편리하고 실용적인 옷들을 추천해드릴게요! ✈️"
        elif "여름" in user_input.lower():
            response_msg = "여름에 딱 맞는 시원하고 가벼운 옷들을 추천해드릴게요! "
        elif "겨울" in user_input.lower():
            response_msg = "겨울에 따뜻하고 스타일리시한 옷들을 추천해드릴게요! ❄️"
        elif "봄" in user_input.lower():
            response_msg = "봄에 어울리는 가벼운 옷들을 추천해드릴게요! "
        elif "가을" in user_input.lower():
            response_msg = "가을에 멋진 옷들을 추천해드릴게요! 🍂"
        else:
            response_msg = "입력해주신 내용을 바탕으로 추천해드릴게요! 😊"
        
        return {
            "success": True,
            "response": response_msg,
            "recommendations": recommendations
        }
    except Exception as e:
        print(f"Error in chat_recommend: {e}")
        # 오류 발생 시 랜덤 추천
        try:
            if not clothing_data:
                load_data()
            fallback_recommendations = random.sample(clothing_data, 2) if clothing_data else []
        except:
            fallback_recommendations = []
        
        return {
            "success": False,
            "response": "죄송합니다. 추천 시스템에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            "recommendations": fallback_recommendations
        }