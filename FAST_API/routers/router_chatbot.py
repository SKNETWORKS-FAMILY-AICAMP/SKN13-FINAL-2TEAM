from fastapi import APIRouter, Form, Depends, Query
from fastapi.responses import JSONResponse
import pandas as pd
import random
import numpy as np
from typing import List, Dict, Optional
import json
from sqlalchemy.orm import Session

from db import get_db
from dependencies import login_required
from crud.user_crud import get_user_by_username
from crud.chat_crud import (
    create_chat_session,
    get_latest_chat_session,
    create_chat_message,
    get_conversation_context,
    get_user_chat_sessions,
    get_chat_session_by_id,
    update_session_name,
    delete_chat_session,
    get_session_messages,
    get_chat_history_for_llm
)
from services.llm_service import LLMService, LLMResponse
from services.intent_analyzer import ChatMessage, IntentResult, analyze_user_intent, analyze_user_intent_with_context
from services.recommendation_engine import ToolResult
from services.product_filter import exact_match_filter, situation_filter
from services.clothing_recommender import recommend_clothing_by_weather
from utils.safe_utils import safe_lower, safe_str

router = APIRouter()

from data_store import clothing_data

# LLM 서비스 초기화
llm_service = LLMService()

# initialize_chatbot_data 함수 제거됨 - main.py에서 통합 관리

# analyze_user_intent 함수는 services/intent_analyzer.py에서 import하여 사용

def exact_match_filter(user_input: str, products: List[Dict]) -> List[Dict]:
    """정확 매칭 필터링 - DB 대분류 기반 + 정확한 카테고리 매칭"""
    # None 값 안전 처리 - safe_lower 사용
    user_input_lower = safe_lower(user_input)
    
    # 정확한 의류 카테고리별 키워드 매핑
    category_keywords = {
        # 상의 카테고리 (업데이트)
        "후드티": ["후드", "후드티", "후드티셔츠", "hood", "hoodie"],
        "셔츠블라우스": ["셔츠", "블라우스", "shirt", "blouse"],
        "긴소매": ["긴소매", "긴팔", "long sleeve", "longsleeve"],
        "반소매": ["반소매", "반팔", "티셔츠", "tshirt", "t-shirt", "tee"],
        "피케카라": ["피케", "카라", "polo", "pique", "collar"],
        "니트스웨터": ["니트", "스웨터", "knit", "sweater", "cardigan"],
        "슬리브리스": ["슬리브리스", "민소매", "나시", "tank", "sleeveless"],
        "애슬레저": ["애슬레저", "운동복", "스포츠", "athleisure", "activewear"],
        
        # 하의 카테고리 (업데이트)
        "데님팬츠": ["데님", "청바지", "jeans", "jean", "denim"],
        "트레이닝조거팬츠": ["트레이닝", "조거", "운동복", "training", "jogger", "track"],
        "코튼팬츠": ["코튼", "면바지", "cotton", "chino"],
        "슈트팬츠슬랙스": ["슈트", "슬랙스", "정장", "suit", "slacks", "dress pants"],
        "숏팬츠": ["숏팬츠", "반바지", "shorts", "short"],
        "레깅스": ["레깅스", "leggings"]
    }
    
    color_keywords = {
        "빨간색": ["red", "빨간", "레드", "빨강"],
        "파란색": ["blue", "파란", "블루", "navy", "네이비", "indigo", "파랑"],
        "검은색": ["black", "검은", "블랙", "검정"],
        "흰색": ["white", "흰", "화이트", "흰색", "화이트"],
        "회색": ["gray", "grey", "회색", "그레이", "회"],
        "베이지": ["beige", "베이지", "베이지색"],
        "갈색": ["brown", "갈색", "브라운", "갈"],
        "노란색": ["yellow", "노란", "옐로", "노랑", "노란색"],
        "초록색": ["green", "초록", "그린", "녹색", "초록색"],
        "분홍색": ["pink", "분홍", "핑크", "분홍색"],
        "보라색": ["purple", "보라", "퍼플", "보라색"],
        "주황색": ["orange", "주황", "오렌지", "주황색"],
        "카키": ["khaki", "카키", "카키색"],
        "민트": ["mint", "민트", "민트색"],
        "네이비": ["navy", "네이비", "남색"],
        "와인": ["wine", "와인", "와인색", "버건디"],
        "올리브": ["olive", "올리브", "올리브색"]
    }
    
    # 사용자 입력에서 카테고리와 색상 찾기
    found_categories = []
    found_colors = []
    
    for category_name, variants in category_keywords.items():
        if any(variant in user_input_lower for variant in variants):
            found_categories.append((category_name, variants))
    
    for color_name, variants in color_keywords.items():
        if any(variant in user_input_lower for variant in variants):
            found_colors.append((color_name, variants))
    
    print(f"=== 정확 매칭 필터링 (DB 기반) ===")
    print(f"입력: '{user_input}'")
    print(f"찾은 카테고리: {[cat[0] for cat in found_categories]}")
    print(f"찾은 색상: {[color[0] for color in found_colors]}")
    
    if not found_categories and not found_colors:
        print("카테고리나 색상 키워드가 없습니다.")
        return []
    
    # 1단계: 대분류로 상의/하의 필터링 (업데이트된 카테고리)
    top_categories = ["후드티", "셔츠블라우스", "긴소매", "반소매", "피케카라", "니트스웨터", "슬리브리스", "애슬레저"]
    bottom_categories = ["데님팬츠", "트레이닝조거팬츠", "코튼팬츠", "슈트팬츠슬랙스", "숏팬츠", "레깅스"]
    
    # 사용자가 원하는 카테고리 타입 확인
    user_wants_top = any(cat[0] in top_categories for cat in found_categories)
    user_wants_bottom = any(cat[0] in bottom_categories for cat in found_categories)
    
    exact_matches = []
    
    for product in products:
        product_text = f"{safe_str(product.get('상품명', ''))} {safe_str(product.get('영어브랜드명', ''))} {safe_str(product.get('대분류', ''))} {safe_str(product.get('소분류', ''))}".lower()
        대분류 = safe_str(product.get('대분류', '')).strip()
        소분류 = safe_str(product.get('소분류', '')).strip()
        
        # 1단계: DB 대분류/소분류로 상의/하의 정확 구분 (소분류 강화)
        is_db_top = (
            대분류 in ["상의", "탑", "TOP", "상의류"] or 
            소분류 in ["상의", "탑", "TOP", "상의류", "후드티", "셔츠블라우스", "긴소매", "피케카라", "니트스웨터", "슬리브리스", "애슬레저", "셔츠", "니트", "후드", "블라우스", "스웨터", "카디건"] or
            (소분류 == "반소매" and any(keyword in product_text for keyword in ["티셔츠", "tshirt", "t-shirt", "tee"]))  # 반소매는 티셔츠일 때만 상의로 인정
        )
        is_db_bottom = (
            대분류 in ["하의", "바텀", "BOTTOM", "하의류", "팬츠", "반바지", "숏팬츠", "쇼츠", "SHORTS", "바지"] or
            소분류 in ["하의", "바텀", "BOTTOM", "하의류", "데님팬츠", "트레이닝조거팬츠", "코튼팬츠", "슈트팬츠슬랙스", "숏팬츠", "레깅스", "팬츠", "바지", "청바지", "데님", "슬랙스"]
        )
        
        # 추가: 제품명에서 직접 하의 키워드 확인 (숏팬츠의 경우)
        # "short"는 "t-shirt"와 구분하기 위해 더 정확한 매칭 사용
        bottom_keywords_in_name = ["숏팬츠", "반바지", "쇼츠", "shorts", "팬츠", "pants", "바지", "슬랙스", "청바지", "데님", "jeans"]
        if any(keyword in product_text for keyword in bottom_keywords_in_name):
            # "shorts" 또는 "쇼츠"가 있지만 "t-shirt", "shirt" 등 상의 키워드는 제외
            if not any(top_keyword in product_text for top_keyword in ["t-shirt", "tshirt", "shirt", "티셔츠", "셔츠"]):
                is_db_bottom = True
        
        # 상의 키워드도 직접 확인
        top_keywords_in_name = ["티셔츠", "tshirt", "t-shirt", "셔츠", "shirt", "니트", "knit", "후드", "hood", "맨투맨", "sweat"]
        if any(keyword in product_text for keyword in top_keywords_in_name):
            is_db_top = True
        
        # 2단계: 사용자가 원하는 상의/하의와 DB 분류가 일치하는지 확인
        category_match = False
        if user_wants_top and is_db_top:
            # 상의 요청 + DB에서도 상의
            if found_categories:
                for category_name, variants in found_categories:
                    if category_name in top_categories:
                        # 정확한 카테고리 매칭 (셔츠 vs 티셔츠 구분)
                        if category_name == "셔츠블라우스":
                            # DB 소분류 컬럼에서 직접 매칭
                            if 소분류 in ["셔츠", "블라우스", "셔츠블라우스"]:
                                category_match = True
                                break
                            # 소분류가 정확하지 않으면 상품명으로 확인
                            else:
                                상품명 = safe_lower(product.get('상품명', ''))
                                has_shirt_word = "셔츠" in 상품명 or "shirt" in 상품명
                                has_tshirt_word = any(word in 상품명 for word in ["티셔츠", "tshirt", "t-shirt", "tee"])
                                has_blouse = "블라우스" in 상품명 or "blouse" in 상품명
                                
                                if (has_shirt_word and not has_tshirt_word) or has_blouse:
                                    category_match = True
                                    break
                                
                        elif category_name == "반소매":
                            # DB 소분류에서 직접 매칭
                            if 소분류 in ["반소매", "반팔"]:
                                category_match = True
                                break
                                
                        elif category_name == "후드티":
                            # DB 소분류에서 직접 매칭
                            if 소분류 in ["후드티", "후드", "후드티셔츠"]:
                                category_match = True
                                break
                                
                        elif category_name == "니트스웨터":
                            # DB 소분류에서 직접 매칭
                            if 소분류 in ["니트", "스웨터", "니트스웨터", "카디건"]:
                                category_match = True
                                break
                                
                        else:
                            # 기타 카테고리는 기존 방식 사용
                            if any(variant in product_text for variant in variants):
                                category_match = True
                                break
            else:
                category_match = True  # 카테고리 조건 없으면 통과
                
        elif user_wants_bottom and is_db_bottom:
            # 하의 요청 + DB에서도 하의
            if found_categories:
                for category_name, variants in found_categories:
                    if category_name in bottom_categories:
                        if category_name == "데님팬츠":
                            # DB 소분류에서 직접 매칭
                            if 소분류 in ["데님", "청바지", "데님팬츠"]:
                                category_match = True
                                break
                                
                        elif category_name == "숏팬츠":
                            # DB 소분류에서 직접 매칭
                            if 소분류 in ["숏팬츠", "반바지", "쇼츠"]:
                                category_match = True
                                break
                                
                        elif category_name == "슈트팬츠슬랙스":
                            # DB 소분류에서 직접 매칭
                            if 소분류 in ["슬랙스", "정장", "슈트팬츠"]:
                                category_match = True
                                break
                                
                        else:
                            # 기타 하의 카테고리는 기존 방식 사용
                            if any(variant in product_text for variant in variants):
                                category_match = True
                                break
            else:
                category_match = True  # 카테고리 조건 없으면 통과
                
        elif not found_categories:
            # 카테고리 조건이 없으면 색상만 확인
            category_match = True
        
        # 3단계: 색상 매칭 (DB 색상 컬럼 직접 매칭)
        color_match = False
        if found_colors:
            # None 값 안전 처리 - safe_str 사용
            db_color_raw = product.get('색상')
            db_color = safe_str(db_color_raw).lower().strip()
            
            for color_name, variants in found_colors:
                # DB 색상 컬럼에서 직접 매칭
                if any(variant.lower() in db_color for variant in variants):
                    color_match = True
                    break
                # 상품명에서도 확인 (DB 색상이 없는 경우 대비)
                elif any(variant in product_text for variant in variants):
                    color_match = True
                    break
        else:
            color_match = True  # 색상 조건이 없으면 통과
        
        # 모든 조건을 만족해야 함
        if category_match and color_match:
            product["is_top"] = is_db_top
            product["is_bottom"] = is_db_bottom
            exact_matches.append(product)
            

    
    print(f"정확 매칭 상품: {len(exact_matches)}개")
    
    # 디버깅: 실제 대분류 값들 확인
    if found_categories and any("숏" in cat[0] or "반바지" in cat[0] for cat in found_categories):
        unique_categories = set()
        for product in products[:100]:  # 처음 100개만 확인
            대분류 = safe_str(product.get('대분류', '')).strip()
            if 대분류 and ("숏" in safe_lower(대분류) or "반바지" in safe_lower(대분류) or "short" in safe_lower(대분류)):
                unique_categories.add(대분류)
        if unique_categories:
            print(f"DB에서 발견된 숏팬츠 관련 대분류: {list(unique_categories)}")
    
    if not exact_matches:
        return []
    
    # 결과 선택
    if user_wants_top and user_wants_bottom:
        # 상의 2개 + 하의 2개
        top_products = [p for p in exact_matches if p.get("is_top", False)]
        bottom_products = [p for p in exact_matches if p.get("is_bottom", False)]
        
        result = []
        if len(top_products) >= 2:
            result.extend(random.sample(top_products, 2))
        elif top_products:
            result.extend(top_products)
            
        if len(bottom_products) >= 2:
            result.extend(random.sample(bottom_products, 2))
        elif bottom_products:
            result.extend(bottom_products)
    elif user_wants_top:
        # 상의만 3개
        top_products = [p for p in exact_matches if p.get("is_top", False)]
        count = min(3, len(top_products))
        result = random.sample(top_products, count) if top_products else []
    elif user_wants_bottom:
        # 하의만 3개  
        bottom_products = [p for p in exact_matches if p.get("is_bottom", False)]
        count = min(3, len(bottom_products))
        result = random.sample(bottom_products, count) if bottom_products else []
    else:
        # 전체에서 4개
        count = min(4, len(exact_matches))
        result = random.sample(exact_matches, count)
    

    
    return result

def get_situation_style(situation: str) -> dict:
    """상황별 스타일 정보"""
    styles = {
        "졸업식": {
            "message": "졸업식은 중요한 자리이기 때문에 깔끔하고 단정한 정장 스타일이 적합합니다. ✨",
            "keywords": ["셔츠", "니트", "정장", "슬랙스", "shirt", "knit", "formal"]
        },
        "데이트": {
            "message": "데이트에는 로맨틱하고 세련된 스타일이 좋아요! 💕",
            "keywords": ["니트", "셔츠", "청바지", "knit", "shirt", "jeans"]
        },
        "면접": {
            "message": "면접에서는 신뢰감을 주는 정장 스타일을 추천드려요! 💼",
            "keywords": ["셔츠", "정장", "슬랙스", "shirt", "formal", "suit"]
        },
        "결혼식": {
            "message": "결혼식에는 예쁘고 격식있는 옷차림이 좋겠어요! 👗",
            "keywords": ["셔츠", "니트", "정장", "shirt", "knit", "formal"]
        },
        "파티": {
            "message": "파티에는 트렌디하고 개성있는 스타일을 추천해요! 🎉",
            "keywords": ["티셔츠", "후드", "청바지", "tshirt", "hood", "jeans"]
        },
        "외출": {
            "message": "외출하기 좋은 편안한 캐주얼 스타일이에요! 👕",
            "keywords": ["티셔츠", "맨투맨", "청바지", "tshirt", "sweat", "jeans"]
        }
    }
    
    return styles.get(situation, styles["외출"])

def situation_filter(situation: str, products: List[Dict]) -> List[Dict]:
    """상황별 필터링"""
    style_info = get_situation_style(situation)
    matched_products = []
    
    print(f"=== {situation} 상황별 필터링 ===")
    print(f"찾는 키워드: {style_info['keywords']}")
    
    for product in products:
        product_text = f"{safe_str(product.get('상품명', ''))} {safe_str(product.get('영어브랜드명', ''))} {safe_str(product.get('대분류', ''))} {safe_str(product.get('소분류', ''))}".lower()
        
        # 상황별 키워드 매칭
        for keyword in style_info["keywords"]:
            if keyword in product_text:
                matched_products.append(product)
                break
    
    print(f"매칭된 상품: {len(matched_products)}개")
    
    if not matched_products:
        return []
    
    # 랜덤으로 4개 선택
    count = min(4, len(matched_products))
    result = random.sample(matched_products, count)
    

    
    return result

def analyze_user_intent_with_context(user_input: str, conversation_context: str = "") -> dict:
    """사용자 의도 분석 (대화 컨텍스트 고려)"""
    # None 값 안전 처리 - safe_lower 사용
    user_input_lower = safe_lower(user_input)
    context_lower = safe_lower(conversation_context)
    
    # 컨텍스트에서 이전 대화 내용 분석
    context_keywords = []
    if conversation_context:
        # 이전 대화에서 언급된 키워드들 추출
        context_keywords = extract_keywords_from_context(conversation_context)
        print(f"컨텍스트 키워드: {context_keywords}")
    
    # 상황별 키워드
    situations = {
        "졸업식": ["졸업식", "졸업", "학위수여식"],
        "결혼식": ["결혼식", "웨딩", "피로연"],
        "데이트": ["데이트", "소개팅", "만남"],
        "면접": ["면접", "취업", "입사", "회사"],
        "파티": ["파티", "클럽", "놀기"],
        "외출": ["외출", "나들이", "쇼핑"],
        "동창회": ["동창회", "모임"]
    }
    
    # 직접 필터링 키워드
    direct_keywords = ["티셔츠", "셔츠", "바지", "청바지", "니트", "후드", 
                      "빨간", "파란", "검은", "흰", "회색", "red", "blue", "black"]
    
    # 컨텍스트와 현재 입력을 모두 고려한 상황별 매칭
    for situation, keywords in situations.items():
        # 현재 입력에서 키워드 확인
        current_match = any(keyword in user_input_lower for keyword in keywords)
        # 컨텍스트에서 키워드 확인
        context_match = any(keyword in context_lower for keyword in keywords)
        
        if current_match or context_match:
            return {
                "type": "SITUATION",
                "situation": situation,
                "original_input": user_input,
                "context_used": context_match
            }
    
    # 직접 필터링 매칭 확인
    if any(keyword in user_input_lower for keyword in direct_keywords):
        return {
            "type": "FILTERING", 
            "original_input": user_input
        }
    
    # 기본값은 일반 검색
    return {
        "type": "FILTERING",
        "original_input": user_input
    }


def extract_keywords_from_context(context: str) -> List[str]:
    """컨텍스트에서 키워드를 추출합니다."""
    keywords = []
    
    # 색상 키워드
    color_keywords = ["빨간", "파란", "검은", "흰", "회색", "red", "blue", "black", "white", "gray"]
    for color in color_keywords:
        if color in safe_lower(context):
            keywords.append(color)
    
    # 의류 키워드
    clothing_keywords = ["티셔츠", "셔츠", "바지", "청바지", "니트", "후드", "shirt", "pants", "jeans"]
    for clothing in clothing_keywords:
        if clothing in safe_lower(context):
            keywords.append(clothing)
    
    return keywords

@router.post("/", response_class=JSONResponse)
async def chat_recommend(
    user_input: str = Form(...),
    session_id: Optional[int] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """챗봇 추천 API - LLM Agent 기반"""
    try:
        print(f"챗봇 요청: {user_input}, 세션: {session_id}, 사용자: {user_name}")
        
        # 사용자 정보 가져오기
        user = get_user_by_username(db, user_name)
        if not user:
            print(f"사용자를 찾을 수 없음: {user_name}")
            return JSONResponse(content={
                "message": "사용자 정보를 찾을 수 없습니다.",
                "products": []
            })
        
        print(f"사용자 ID: {user.id}")
        
        # 세션 처리
        if session_id:
            # 기존 세션 사용
            chat_session = get_chat_session_by_id(db, session_id, user.id)
            if not chat_session:
                print(f"세션을 찾을 수 없음: {session_id}")
                return JSONResponse(content={
                    "message": "세션을 찾을 수 없습니다.",
                    "products": []
                })
        else:
            # 항상 새로운 세션 생성 (기존 세션 재사용하지 않음)
            session_name = f"{user_input[:20]}{'...' if len(user_input) > 20 else ''}"
            chat_session = create_chat_session(db, user.id, session_name)
            print(f"새 세션 생성: {chat_session.id} - {session_name}")
        
        # 사용자 메시지 저장
        user_message = create_chat_message(db, chat_session.id, "user", user_input)
        print(f"사용자 메시지 저장: {user_message.id}")
        
        # 대화 컨텍스트 가져오기 (최근 3쌍)
        conversation_context = get_conversation_context(db, chat_session.id, max_messages=6)
        print(f"대화 컨텍스트: {conversation_context}")
        
        # LLM Agent를 통해 의도 분석 및 응답 생성 (분리된 서비스 사용)
        try:
            # ChatMessage 리스트로 변환
            chat_history_for_llm = []
            if conversation_context:
                # 간단한 형태로 변환 (실제로는 더 복잡한 파싱이 필요할 수 있음)
                chat_history_for_llm = [ChatMessage(role="user", content=conversation_context)]
            
            llm_response: LLMResponse = await llm_service.analyze_intent_and_call_tool(
                user_input=user_input,
                chat_history=chat_history_for_llm,
                available_products=list(clothing_data.values()) if clothing_data else [],
                db=db,
                user_id=user.id,
                latitude=latitude,
                longitude=longitude
            )
            
            message = llm_response.final_message
            products = llm_response.products
            print(f"DEBUG: llm_response.final_message: {llm_response.final_message}") # NEW PRINT

            # 날씨 의도 처리 및 의류 추천 통합
            if llm_response.intent_result.intent == "weather":
                import re
                temperature = None
                weather_description = None
                
                try:
                    # 1. LLM 응답 메시지에서 기온 및 날씨 상황 추출 (문자열 조작 사용)
                    temp_start_idx = llm_response.final_message.find('🌡️ **기온**: ')
                    temp_end_idx = llm_response.final_message.find('°C', temp_start_idx)
                    if temp_start_idx != -1 and temp_end_idx != -1:
                        temperature_str = llm_response.final_message[temp_start_idx + len('🌡️ **기온**: '):temp_end_idx].strip()
                        temperature = float(temperature_str)
                    else:
                        temperature = None

                    weather_desc_start_idx = llm_response.final_message.find('✨ **날씨 상황**: ')
                    if weather_desc_start_idx != -1:
                        weather_description = llm_response.final_message[weather_desc_start_idx + len('✨ **날씨 상황**: '):].strip()
                    else:
                        weather_description = None
                    
                    print(f"DEBUG: Extracted temperature: {temperature}, weather_description: {weather_description})")
                except Exception as e:
                    import traceback
                    print(f"ERROR: Regex parsing for weather failed. Exception Type: {type(e).__name__}, Message: {e}")
                    print(f"TRACEBACK: {traceback.format_exc()}")
                    # Fallback if parsing fails
                    message = llm_response.final_message + "\n\n날씨 정보 파싱 중 오류가 발생했습니다."
                    products = []
                    # Skip further processing and return
                    bot_message = create_chat_message(db, chat_session.id, "bot", message)
                    print(f"봇 메시지 저장: {bot_message.id}")
                    return JSONResponse(content={
                        "message": message,
                        "products": products,
                        "session_id": chat_session.id,
                        "session_name": chat_session.session_name
                    })

                # 2. 사용자 성별 가져오기 (user 객체에 gender 속성이 있다고 가정)
                raw_gender = user.gender if hasattr(user, 'gender') else None
                if raw_gender == "male":
                    user_gender = "남성"
                elif raw_gender == "female":
                    user_gender = "여성"
                else: # "unisex" or None
                    user_gender = "남성" # Default for unisex or unspecified

                if weather_description is not None: # 날씨 상황이 추출된 경우에만 추천 진행
                    try:
                        # 3. 의류 추천 함수 호출 (날씨 상황 전달)
                        recommended_clothing = recommend_clothing_by_weather(weather_description, user_gender)
                        print(f"DEBUG: recommended_clothing from recommender: {recommended_clothing}")
                    except Exception as e:
                        print(f"ERROR: recommend_clothing_by_weather failed: {e}")
                        message = llm_response.final_message + "\n\n의류 추천 생성 중 오류가 발생했습니다."
                        products = []
                        # Skip further processing and return
                        bot_message = create_chat_message(db, chat_session.id, "bot", message)
                        print(f"봇 메시지 저장: {bot_message.id}")
                        return JSONResponse(content={
                            "message": message,
                            "products": products,
                            "session_id": chat_session.id,
                            "session_name": chat_session.session_name
                        })

                    try:
                        # 4. 추천 의류를 자연어 메시지로 변환
                        clothing_str_parts = []
                        for category, items in recommended_clothing.items():
                            if items:
                                clothing_str_parts.append(f"{category}: {', '.join(items)}")
                        
                        clothing_recommendation_message = ""
                        if clothing_str_parts:
                            clothing_recommendation_message = f"\n\n오늘 날씨에는 {', '.join(clothing_str_parts)}을(를) 추천해 드려요! 👕👖"
                        
                        # 기존 날씨 메시지에서 불필요한 부분 제거하고 추천 메시지 추가
                        message = llm_response.final_message.strip()
                        message += clothing_recommendation_message
                    except Exception as e:
                        print(f"ERROR: Clothing recommendation message formatting failed: {e}")
                        message = llm_response.final_message + "\n\n추천 메시지 구성 중 오류가 발생했습니다."
                        products = []
                        # Skip further processing and return
                        bot_message = create_chat_message(db, chat_session.id, "bot", message)
                        print(f"봇 메시지 저장: {bot_message.id}")
                        return JSONResponse(content={
                            "message": message,
                            "products": products,
                            "session_id": chat_session.id,
                            "session_name": chat_session.session_name
                        })
                else:
                    # 날씨 상황 추출 실패 시 기존 메시지 유지
                    message = llm_response.final_message
            # 날씨 의도가 아닐 경우 기존 메시지 유지
            else:
                message = llm_response.final_message
            
            print(f"LLM 응답 - 의도: {llm_response.intent_result.intent}, 제품 수: {len(products)}")
            
            # 상품 링크 디버깅
            if products:
                print("=== 상품 링크 디버깅 ===")
                for i, product in enumerate(products[:3]):  # 처음 3개만 확인
                    print(f"상품 {i+1}: {product.get('상품명', 'N/A')}")
                    print(f"  - 상품링크: '{product.get('상품링크', 'N/A')}'")
                    print(f"  - 링크: '{product.get('링크', 'N/A')}'")
                    print(f"  - URL: '{product.get('URL', 'N/A')}'")
                    print(f"  - 모든 키: {list(product.keys())}")
                    print("---")
            
        except Exception as e:
            print(f"LLM 처리 오류: {e}")
            # LLM 오류 시 기본 응답
            message = f"'{user_input}'에 대한 의류를 찾아보겠습니다! 🔍"
            products = []
        
        # 챗봇 응답 저장
        bot_message = create_chat_message(db, chat_session.id, "bot", message)
        print(f"봇 메시지 저장: {bot_message.id}")
        
        return JSONResponse(content={
            "message": message,
            "products": products,
            "session_id": chat_session.id,
            "session_name": chat_session.session_name
        })
        
    except Exception as e:
        print(f"챗봇 오류: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={
            "message": "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.",
            "products": []
        })

@router.get("/sessions", response_class=JSONResponse)
async def get_chat_sessions(
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """사용자의 모든 챗봇 세션을 조회합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "sessions": []
            })
        
        sessions = get_user_chat_sessions(db, user.id, limit=50)
        
        session_list = []
        for session in sessions:
            # 각 세션의 메시지 수 계산
            messages = get_session_messages(db, session.id, user.id)
            
            session_list.append({
                "id": session.id,
                "name": session.session_name,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "message_count": len(messages)
            })
        
        return JSONResponse(content={
            "success": True,
            "message": "세션 목록을 성공적으로 조회했습니다.",
            "sessions": session_list
        })
        
    except Exception as e:
        print(f"세션 목록 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 목록 조회 중 오류가 발생했습니다.",
            "sessions": []
        })

@router.get("/session/{session_id}/messages", response_class=JSONResponse)
async def get_session_messages_api(
    session_id: int,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """특정 세션의 메시지들을 조회합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "messages": []
            })
        
        messages = get_session_messages(db, session_id, user.id)
        
        return JSONResponse(content={
            "success": True,
            "message": "세션 메시지를 성공적으로 조회했습니다.",
            "messages": messages
        })
        
    except Exception as e:
        print(f"세션 메시지 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 메시지 조회 중 오류가 발생했습니다.",
            "messages": []
        })

@router.put("/session/{session_id}/name", response_class=JSONResponse)
async def update_session_name_api(
    session_id: int,
    new_name: str = Form(...),
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """세션 이름을 변경합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다."
            })
        
        success = update_session_name(db, session_id, user.id, new_name)
        
        if success:
            return JSONResponse(content={
                "success": True,
                "message": "세션 이름이 성공적으로 변경되었습니다."
            })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "세션을 찾을 수 없거나 권한이 없습니다."
            })
        
    except Exception as e:
        print(f"세션 이름 변경 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 이름 변경 중 오류가 발생했습니다."
        })

@router.delete("/session/{session_id}", response_class=JSONResponse)
async def delete_session_api(
    session_id: int,
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """세션을 삭제합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다."
            })
        
        success = delete_chat_session(db, session_id, user.id)
        
        if success:
            return JSONResponse(content={
                "success": True,
                "message": "세션이 성공적으로 삭제되었습니다."
            })
        else:
            return JSONResponse(content={
                "success": False,
                "message": "세션을 찾을 수 없거나 권한이 없습니다."
            })
        
    except Exception as e:
        print(f"세션 삭제 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "세션 삭제 중 오류가 발생했습니다."
        })

@router.get("/history", response_class=JSONResponse)
async def get_chat_history(
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """사용자의 챗봇 대화 기록을 조회합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "history": []
            })
        
        from crud.chat_crud import get_user_chat_history
        
        # 최근 20개 메시지 조회
        messages = get_user_chat_history(db, user.id, limit=20)
        
        # 메시지 형식 변환
        history = []
        for msg in messages:
            history.append({
                "id": msg.id,
                "type": msg.message_type,
                "text": msg.text,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            })
        
        return JSONResponse(content={
            "success": True,
            "message": "대화 기록을 성공적으로 조회했습니다.",
            "history": history
        })
        
    except Exception as e:
        print(f"대화 기록 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "대화 기록 조회 중 오류가 발생했습니다.",
            "history": []
        })

@router.get("/recommendations", response_class=JSONResponse)
async def get_user_recommendations(
    db: Session = Depends(get_db),
    user_name: str = Depends(login_required)
):
    """사용자의 추천 기록을 조회합니다."""
    try:
        user = get_user_by_username(db, user_name)
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다.",
                "recommendations": []
            })
        
        from crud.recommendation_crud import get_user_recommendations
        
        # 최근 50개 추천 기록 조회
        recommendations = get_user_recommendations(db, user.id, limit=50)
        
        # 추천 기록 형식 변환
        recommendation_list = []
        for rec in recommendations:
            recommendation_list.append({
                "id": rec.id,
                "item_id": rec.item_id,
                "query": rec.query,
                "reason": rec.reason,
                "created_at": rec.created_at.isoformat() if rec.created_at else None
            })
        
        return JSONResponse(content={
            "success": True,
            "message": "추천 기록을 성공적으로 조회했습니다.",
            "recommendations": recommendation_list
        })
        
    except Exception as e:
        print(f"추천 기록 조회 오류: {e}")
        return JSONResponse(content={
            "success": False,
            "message": "추천 기록 조회 중 오류가 발생했습니다.",
            "recommendations": []
        }) 