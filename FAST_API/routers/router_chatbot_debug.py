from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
import pandas as pd
import random
import numpy as np
from typing import List, Dict
import traceback

router = APIRouter()

# 전역 변수로 데이터 저장
clothing_data = []

def initialize_chatbot_data_debug():
    """챗봇 데이터 초기화 - 디버깅 버전"""
    global clothing_data
    try:
        print("=== 디버깅: 데이터 초기화 시작 ===")
        from sqlalchemy import create_engine
        
        # PostgreSQL 연결
        DB_USER = "postgres"
        DB_PASSWORD = "1234"
        DB_HOST = "localhost"
        DB_PORT = "5432"
        DB_NAME = "musinsa"
        
        print(f"DB 연결 시도: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        print("SQL 쿼리 실행 중...")
        df = pd.read_sql("SELECT * FROM product LIMIT 100", con=engine)  # 테스트용으로 100개만
        print(f"DB에서 가져온 행 수: {len(df)}")
        
        df = df.replace({np.nan: None})
        
        # 이미지 URL 정리
        def fix_image_url(url):
            if pd.isna(url) or url is None:
                return ""
            url = str(url).strip()
            if url.startswith("https:/images/goods_img/"):
                url = url.replace("https:/", "").lstrip("/")
                return f"https://image.msscdn.net/thumbnails/{url}"
            return url
        
        df["사진"] = df["사진"].apply(fix_image_url)
        raw_data = df.to_dict("records")
        
        # 데이터 매핑
        clothing_data = []
        for i, item in enumerate(raw_data):
            if i < 3:  # 첫 3개 항목의 상세 정보 출력
                print(f"샘플 데이터 {i+1}: {item.get('제품이름', 'N/A')[:30]}...")
                
            mapped_item = {
                "상품명": item.get("제품이름", "") or "",
                "브랜드": item.get("브랜드", "") or "",
                "가격": int(item.get("할인가", item.get("원가", 0)) or 0),
                "사진": item.get("사진", "") or "",
                "제품대분류": item.get("제품대분류", "") or "",
                "제품소분류": item.get("제품소분류", "") or ""
            }
            clothing_data.append(mapped_item)
            
        print(f"=== 디버깅: 데이터 로드 완료: {len(clothing_data)}개 상품 ===")
        
    except Exception as e:
        print(f"=== 디버깅: 데이터 로드 실패 ===")
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {str(e)}")
        traceback.print_exc()
        clothing_data = []

def simple_filter_debug(user_input: str, products: List[Dict]) -> List[Dict]:
    """간단한 필터링 - 디버깅 버전"""
    print(f"=== 디버깅: 필터링 시작 ===")
    print(f"입력: '{user_input}'")
    print(f"전체 상품 수: {len(products)}")
    
    if not products:
        print("상품 데이터가 없습니다!")
        return []
    
    # 간단한 키워드 매칭
    user_input_lower = user_input.lower()
    filtered = []
    
    keywords = ["티셔츠", "셔츠", "바지", "청바지", "니트", "후드", "맨투맨"]
    colors = ["빨간", "파란", "검은", "흰", "회색", "red", "blue", "black", "white"]
    
    found_keywords = [k for k in keywords if k in user_input_lower]
    found_colors = [c for c in colors if c in user_input_lower]
    
    print(f"발견된 키워드: {found_keywords}")
    print(f"발견된 색상: {found_colors}")
    
    # 키워드가 있으면 매칭, 없으면 랜덤
    if found_keywords or found_colors:
        for product in products:
            product_text = f"{product.get('상품명', '')} {product.get('제품대분류', '')} {product.get('제품소분류', '')}".lower()
            
            for keyword in found_keywords:
                if keyword in product_text:
                    filtered.append(product)
                    break
            
            if len(filtered) >= 3:
                break
    
    if not filtered:
        print("매칭되는 상품이 없어서 랜덤 선택")
        filtered = random.sample(products, min(3, len(products)))
    
    print(f"최종 선택된 상품 수: {len(filtered)}")
    for i, product in enumerate(filtered):
        print(f"상품 {i+1}: {product.get('제품이름', 'N/A')[:30]}...")
    
    print(f"=== 디버깅: 필터링 완료 ===")
    return filtered

@router.post("/chat-debug", response_class=JSONResponse)
async def chat_recommend_debug(user_input: str = Form(...)):
    """챗봇 추천 API - 디버깅 버전"""
    print(f"\n=== 디버깅: API 호출 시작 ===")
    print(f"받은 입력: '{user_input}'")
    
    try:
        # 데이터 확인
        if not clothing_data:
            print("데이터가 없어서 초기화 시도")
            initialize_chatbot_data_debug()
        
        print(f"현재 데이터 개수: {len(clothing_data)}")
        
        if not clothing_data:
            print("데이터 초기화 실패!")
            return JSONResponse(content={
                "message": "데이터 로딩에 실패했습니다.",
                "products": []
            })
        
        # 필터링
        recommendations = simple_filter_debug(user_input, clothing_data)
        
        print(f"최종 추천 상품 수: {len(recommendations)}")
        
        result = {
            "message": f"[디버그] '{user_input}' 검색 결과입니다! 😊",
            "products": recommendations
        }
        
        print(f"=== 디버깅: API 응답 준비 완료 ===")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"=== 디버깅: 오류 발생 ===")
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {str(e)}")
        traceback.print_exc()
        
        return JSONResponse(content={
            "message": f"[디버그] 오류 발생: {str(e)}",
            "products": []
        })

@router.get("/chat-test")
async def test_endpoint():
    """간단한 테스트 엔드포인트"""
    return JSONResponse(content={
        "message": "디버그 라우터가 정상 작동합니다!",
        "data_count": len(clothing_data),
        "status": "OK"
    }) 