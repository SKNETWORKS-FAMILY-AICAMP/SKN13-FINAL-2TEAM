from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
import pandas as pd
import random
import numpy as np
from typing import List, Dict, Optional
import json

router = APIRouter()

# 전역 변수로 데이터 저장
clothing_data = []

def initialize_chatbot_data():
    """챗봇 데이터 초기화"""
    global clothing_data
    try:
        from sqlalchemy import create_engine
        
        # PostgreSQL 연결
        DB_USER = "postgres"
        DB_PASSWORD = "1234"
        DB_HOST = "localhost"
        DB_PORT = "5432"
        DB_NAME = "musinsa"
        
        engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        df = pd.read_sql("SELECT * FROM product", con=engine)
        df = df.replace({np.nan: None})
        
        # 이미지 URL 정리
        def fix_image_url(url):
            if pd.isna(url) or url is None:
                return ""
            url = str(url).strip()
            if url.startswith("https:/images/goods_img/") or url.startswith("images/goods_img/") or url.startswith("/images/goods_img/"):
                url = url.replace("https:/", "").lstrip("/")
                return f"https://image.msscdn.net/thumbnails/{url}"
            if url.startswith("https://image.msscdn.net"):
                return url
            return url
        
        df["사진"] = df["사진"].apply(fix_image_url)
        raw_data = df.to_dict("records")
        
        # 데이터 매핑
        clothing_data = []
        for item in raw_data:
            mapped_item = {
                "상품명": item.get("제품이름", "") or "",
                "상품영문명": item.get("제품영문이름", "") or "",
                "카테고리": f"{item.get('제품대분류', '') or ''} - {item.get('제품소분류', '') or ''}",
                "브랜드": item.get("브랜드", "") or "",
                "브랜드영문": item.get("브랜드영문", "") or "",
                "가격": int(item.get("할인가", item.get("원가", 0)) or 0),
                "사진": item.get("사진", "") or "",
                "제품대분류": item.get("제품대분류", "") or "",
                "제품소분류": item.get("제품소분류", "") or ""
            }
            clothing_data.append(mapped_item)
            
        print(f"챗봇 데이터 로드 완료: {len(clothing_data)}개 상품")
        
    except Exception as e:
        print(f"챗봇 데이터 로드 실패: {e}")
        clothing_data = []

def analyze_user_intent(user_input: str) -> dict:
    """사용자 의도 분석"""
    user_input_lower = user_input.lower()
    
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
    
    # 상황별 매칭 확인
    for situation, keywords in situations.items():
        if any(keyword in user_input_lower for keyword in keywords):
            return {
                "type": "SITUATION",
                "situation": situation,
                "original_input": user_input
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

def exact_match_filter(user_input: str, products: List[Dict]) -> List[Dict]:
    """정확 매칭 필터링 - DB 제품대분류 기반 + 정확한 카테고리 매칭"""
    user_input_lower = user_input.lower()
    
    # 정확한 의류 카테고리별 키워드 매핑
    category_keywords = {
        # 상의 카테고리
        "맨투맨/스웨트": ["맨투맨", "스웨트", "sweat", "sweatshirt"],
        "후드 티셔츠": ["후드", "후드티", "hood", "hoodie"],
        "셔츠/블라우스": ["셔츠", "블라우스", "shirt", "blouse"],
        "긴소매 티셔츠": ["긴소매", "긴팔", "long sleeve", "longsleeve"],
        "반소매 티셔츠": ["반소매", "반팔", "티셔츠", "tshirt", "t-shirt", "tee"],
        "피케/카라 티셔츠": ["피케", "카라", "polo", "pique"],
        "카라 티셔츠": ["카라", "collar"],
        "니트/스웨터": ["니트", "스웨터", "knit", "sweater", "cardigan"],
        "민소매 티셔츠": ["민소매", "나시", "tank", "sleeveless"],
        
        # 하의 카테고리  
        "데님 팬츠": ["데님", "청바지", "jeans", "jean", "denim"],
        "트레이닝/조거 팬츠": ["트레이닝", "조거", "운동복", "training", "jogger", "track"],
        "코튼 팬츠": ["코튼", "면바지", "cotton", "chino"],
        "슈트 팬츠/슬랙스": ["슈트", "슬랙스", "정장", "suit", "slacks", "dress pants"],
        "숏 팬츠": ["숏팬츠", "반바지", "shorts", "short"],
        "레깅스": ["레깅스", "leggings"],
        "점프 슈트/오버올": ["점프슈트", "오버올", "jumpsuit", "overall"]
    }
    
    color_keywords = {
        "빨간색": ["red", "빨간", "레드"],
        "파란색": ["blue", "파란", "블루", "navy", "네이비", "indigo"],
        "검은색": ["black", "검은", "블랙"],
        "흰색": ["white", "흰", "화이트"],
        "회색": ["gray", "grey", "회색", "그레이"]
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
    
    # 1단계: 제품대분류로 상의/하의 필터링
    top_categories = ["맨투맨/스웨트", "후드 티셔츠", "셔츠/블라우스", "긴소매 티셔츠", "반소매 티셔츠", "피케/카라 티셔츠", "카라 티셔츠", "니트/스웨터", "민소매 티셔츠"]
    bottom_categories = ["데님 팬츠", "트레이닝/조거 팬츠", "코튼 팬츠", "슈트 팬츠/슬랙스", "숏 팬츠", "레깅스", "점프 슈트/오버올"]
    
    # 사용자가 원하는 카테고리 타입 확인
    user_wants_top = any(cat[0] in top_categories for cat in found_categories)
    user_wants_bottom = any(cat[0] in bottom_categories for cat in found_categories)
    
    exact_matches = []
    
    for product in products:
        product_text = f"{product.get('상품명', '')} {product.get('상품영문명', '')} {product.get('제품대분류', '')} {product.get('제품소분류', '')}".lower()
        대분류 = product.get('제품대분류', '').strip()
        소분류 = product.get('제품소분류', '').strip()
        
        # 1단계: DB 제품대분류/소분류로 상의/하의 정확 구분
        is_db_top = (대분류 in ["상의", "탑", "TOP", "상의류"] or 
                    소분류 in ["상의", "탑", "TOP", "상의류"])
        is_db_bottom = (대분류 in ["하의", "바텀", "BOTTOM", "하의류", "팬츠", "반바지", "숏팬츠", "쇼츠", "SHORTS", "바지"] or
                       소분류 in ["하의", "바텀", "BOTTOM", "하의류", "팬츠", "반바지", "숏팬츠", "쇼츠", "SHORTS", "바지"])
        
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
                        if category_name == "셔츠/블라우스":
                            if any(variant in product_text for variant in variants) and "티셔츠" not in product_text:
                                category_match = True
                                break
                        elif category_name == "반소매 티셔츠":
                            if any(variant in product_text for variant in variants) and "셔츠" not in product_text.replace("티셔츠", ""):
                                category_match = True
                                break
                        else:
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
                        if any(variant in product_text for variant in variants):
                            category_match = True
                            break
            else:
                category_match = True  # 카테고리 조건 없으면 통과
                
        elif not found_categories:
            # 카테고리 조건이 없으면 색상만 확인
            category_match = True
        
        # 3단계: 색상 매칭
        color_match = False
        if found_colors:
            for color_name, variants in found_colors:
                if any(variant in product_text for variant in variants):
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
    
    # 디버깅: 실제 제품대분류 값들 확인
    if found_categories and any("숏" in cat[0] or "반바지" in cat[0] for cat in found_categories):
        unique_categories = set()
        for product in products[:100]:  # 처음 100개만 확인
            대분류 = product.get('제품대분류', '').strip()
            if 대분류 and ("숏" in 대분류.lower() or "반바지" in 대분류.lower() or "short" in 대분류.lower()):
                unique_categories.add(대분류)
        if unique_categories:
            print(f"DB에서 발견된 숏팬츠 관련 제품대분류: {list(unique_categories)}")
    
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
    
    for i, p in enumerate(result):
        category = "상의" if p.get("is_top") else ("하의" if p.get("is_bottom") else "기타")
        print(f"최종 선택 {i+1}: [{category}] {p.get('상품명', 'N/A')[:30]}... (대분류: {p.get('제품대분류', 'N/A')})")
    
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
        product_text = f"{product.get('상품명', '')} {product.get('상품영문명', '')} {product.get('제품대분류', '')} {product.get('제품소분류', '')}".lower()
        
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
    
    for i, p in enumerate(result):
        print(f"상황별 선택 {i+1}: {p.get('상품명', 'N/A')[:25]}...")
    
    return result

@router.post("/chat", response_class=JSONResponse)
async def chat_recommend(user_input: str = Form(...)):
    """챗봇 추천 API - 정확 매칭 + 랜덤"""
    try:
        if not clothing_data:
            initialize_chatbot_data()
        
        # 의도 분석
        intent = analyze_user_intent(user_input)
        print(f"=== 의도 분석 ===")
        print(f"타입: {intent['type']}, 상황: {intent.get('situation', 'N/A')}")
        
        if intent["type"] == "FILTERING":
            # 직접 필터링
            recommendations = exact_match_filter(user_input, clothing_data)
            if recommendations:
                message = "요청하신 조건에 맞는 상품을 찾았어요! 😊"
            else:
                message = "죄송해요, 요청하신 조건에 맞는 상품을 찾을 수 없어요. 😅 다른 키워드로 다시 검색해보시겠어요?"
                
        elif intent["type"] == "SITUATION":
            # 상황별 추천
            recommendations = situation_filter(intent["situation"], clothing_data)
            style_info = get_situation_style(intent["situation"])
            if recommendations:
                message = style_info["message"]
            else:
                message = f"{intent['situation']} 상황에 맞는 상품을 찾을 수 없어요. 😅 다른 상황으로 검색해보시겠어요?"
        
        return JSONResponse(content={
            "message": message,
            "products": recommendations
        })
        
    except Exception as e:
        print(f"챗봇 오류: {e}")
        return JSONResponse(content={
            "message": "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.",
            "products": []
        }) 