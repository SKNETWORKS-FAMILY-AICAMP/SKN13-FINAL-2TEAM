import random
from typing import List, Dict
from utils.safe_utils import safe_lower, safe_str

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
                if any(safe_lower(variant) in db_color for variant in variants):
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
