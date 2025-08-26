from typing import Optional, Dict

from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from models.models_auth import User
from models.models_mypage import UserPreference
from models.models_jjim import Jjim


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, password=password, email="", gender=None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def upsert_user_preference(
    db: Session,
    user_id: int,
    *,
    height: Optional[int] = None,
    weight: Optional[int] = None,
    preferred_color: Optional[str] = None,
    preferred_style: Optional[str] = None,
) -> UserPreference:
    stmt = select(UserPreference).where(UserPreference.user_id == user_id)
    pref = db.execute(stmt).scalar_one_or_none()
    if pref is None:
        pref = UserPreference(
            user_id=user_id,
            height=height,
            weight=weight,
            preferred_color=preferred_color,
            preferred_style=preferred_style,
        )
        db.add(pref)
    else:
        pref.height = height
        pref.weight = weight
        pref.preferred_color = preferred_color
        pref.preferred_style = preferred_style

    db.commit()
    db.refresh(pref)
    return pref


def get_preference_by_user_id(db: Session, user_id: int) -> Optional[UserPreference]:
    stmt = select(UserPreference).where(UserPreference.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def add_jjim(db: Session, user_id: int, product_id: str) -> Jjim:
    # 중복 방지
    stmt = select(Jjim).where(Jjim.user_id == user_id, Jjim.product_id == product_id)
    exists = db.execute(stmt).scalar_one_or_none()
    if exists:
        return exists
    rec = Jjim(user_id=user_id, product_id=str(product_id))
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def remove_jjim(db: Session, user_id: int, product_id: str) -> bool:
    stmt = select(Jjim).where(Jjim.user_id == user_id, Jjim.product_id == product_id)
    rec = db.execute(stmt).scalar_one_or_none()
    if not rec:
        return False
    db.delete(rec)
    db.commit()
    return True


def list_jjim_product_ids(db: Session, user_id: int) -> list[str]:
    rows = db.execute(select(Jjim.product_id).where(Jjim.user_id == user_id)).all()
    return [r[0] for r in rows]


def remove_jjim_bulk(db: Session, user_id: int, product_ids: list[str]) -> int:
    if not product_ids:
        return 0
    stmt = delete(Jjim).where(Jjim.user_id == user_id, Jjim.product_id.in_([str(pid) for pid in product_ids]))
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


def get_trending_products(db: Session, limit: int = 20) -> list[dict]:
    """
    전체 유저의 찜 데이터를 집계하여 인기 상품을 반환합니다.
    
    Args:
        db: 데이터베이스 세션
        limit: 반환할 상품 수 (기본값: 20)
    
    Returns:
        찜 횟수 순으로 정렬된 상품 정보 리스트
    """
    from sqlalchemy import func
    
    # 상품별 찜 횟수 집계
    stmt = (
        select(
            Jjim.product_id,
            func.count(Jjim.id).label('jjim_count')
        )
        .group_by(Jjim.product_id)
        .order_by(func.count(Jjim.id).desc())
        .limit(limit)
    )
    
    trending_data = db.execute(stmt).all()
    
    # 결과를 딕셔너리 형태로 변환
    trending_products = [
        {
            'product_id': row.product_id,
            'jjim_count': row.jjim_count
        }
        for row in trending_data
    ]
    
    return trending_products


def get_user_jjim_count(db: Session, product_id: str) -> int:
    """
    특정 상품의 찜 횟수를 반환합니다.
    
    Args:
        db: 데이터베이스 세션
        product_id: 상품 ID
    
    Returns:
        찜 횟수
    """
    from sqlalchemy import func
    
    stmt = select(func.count(Jjim.id)).where(Jjim.product_id == product_id)
    result = db.execute(stmt).scalar()
    return result or 0


def get_personalized_recommendations(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    """
    사용자 맞춤형 추천 상품을 반환합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        limit: 반환할 상품 수 (기본값: 20)
    
    Returns:
        사용자 맞춤형 추천 상품 정보 리스트
    """
    from sqlalchemy import func, and_
    
    # 1. 사용자의 키와 체중 정보 가져오기
    user_pref = get_preference_by_user_id(db, user_id)
    if not user_pref or user_pref.height is None or user_pref.weight is None:
        # 사용자 정보가 없으면 전체 인기 상품 반환
        return get_trending_products(db, limit)
    
    user_height = user_pref.height
    user_weight = user_pref.weight
    
    # 2. 키와 체중 ±5 범위에 속하는 사용자들 찾기
    similar_users_stmt = (
        select(UserPreference.user_id)
        .where(
            and_(
                UserPreference.height.between(user_height - 5, user_height + 5),
                UserPreference.weight.between(user_weight - 5, user_weight + 5),
                UserPreference.user_id != user_id  # 자기 자신 제외
            )
        )
    )
    
    similar_users = db.execute(similar_users_stmt).all()
    similar_user_ids = [row[0] for row in similar_users]
    
    if not similar_user_ids:
        # 유사한 사용자가 없으면 전체 인기 상품 반환
        return get_trending_products(db, limit)
    
    # 3. 유사한 사용자들이 찜한 상품들 가져오기
    jjim_stmt = (
        select(
            Jjim.product_id,
            func.count(Jjim.id).label('jjim_count')
        )
        .where(Jjim.user_id.in_(similar_user_ids))
        .group_by(Jjim.product_id)
        .order_by(func.count(Jjim.id).desc())
    )
    
    jjim_data = db.execute(jjim_stmt).all()
    
    # 4. 결과를 딕셔너리 형태로 변환
    recommended_products = [
        {
            'product_id': row.product_id,
            'jjim_count': row.jjim_count
        }
        for row in jjim_data
    ]
    
    # 5. 사용자가 이미 찜한 상품 제외
    user_jjim_ids = set(list_jjim_product_ids(db, user_id))
    recommended_products = [
        product for product in recommended_products 
        if product['product_id'] not in user_jjim_ids
    ]
    
    # 6. 상위 limit개만 반환
    return recommended_products[:limit]


def get_color_filtered_recommendations(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    """
    사용자 선호 색상을 고려한 맞춤형 추천 상품을 반환합니다.
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        limit: 반환할 상품 수 (기본값: 20)
    
    Returns:
        색상 필터링된 맞춤형 추천 상품 정보 리스트
    """
    from sqlalchemy import func, and_, or_
    
    # 1. 사용자의 키와 체중 정보 가져오기
    user_pref = get_preference_by_user_id(db, user_id)
    if not user_pref or user_pref.height is None or user_pref.weight is None:
        # 사용자 정보가 없으면 전체 인기 상품 반환
        return get_trending_products(db, limit)
    
    user_height = user_pref.height
    user_weight = user_pref.weight
    user_preferred_color = user_pref.preferred_color
    
    # 2. 키와 체중 ±5 범위에 속하는 사용자들 찾기
    similar_users_stmt = (
        select(UserPreference.user_id)
        .where(
            and_(
                UserPreference.height.between(user_height - 5, user_height + 5),
                UserPreference.weight.between(user_weight - 5, user_weight + 5),
                UserPreference.user_id != user_id  # 자기 자신 제외
            )
        )
    )
    
    similar_users = db.execute(similar_users_stmt).all()
    similar_user_ids = [row[0] for row in similar_users]
    
    if not similar_user_ids:
        # 유사한 사용자가 없으면 전체 인기 상품 반환
        return get_trending_products(db, limit)
    
    # 3. 유사한 사용자들이 찜한 상품들 가져오기
    jjim_stmt = (
        select(
            Jjim.product_id,
            func.count(Jjim.id).label('jjim_count')
        )
        .where(Jjim.user_id.in_(similar_user_ids))
        .group_by(Jjim.product_id)
        .order_by(func.count(Jjim.id).desc())
    )
    
    jjim_data = db.execute(jjim_stmt).all()
    
    # 4. 결과를 딕셔너리 형태로 변환
    recommended_products = [
        {
            'product_id': row.product_id,
            'jjim_count': row.jjim_count
        }
        for row in jjim_data
    ]
    
    # 5. 사용자가 이미 찜한 상품 제외
    user_jjim_ids = set(list_jjim_product_ids(db, user_id))
    recommended_products = [
        product for product in recommended_products 
        if product['product_id'] not in user_jjim_ids
    ]
    
    # 6. 상위 limit개만 반환
    return recommended_products[:limit]


def filter_products_by_color(products: list[dict], preferred_color: str) -> list[dict]:
    """
    사용자 선호 색상에 따라 상품을 필터링합니다.
    
    Args:
        products: 상품 리스트
        preferred_color: 선호 색상
    
    Returns:
        색상 필터링된 상품 리스트
    """
    if not preferred_color:
        return products
    
    # 색상 매칭 로직 (간단한 키워드 매칭)
    color_keywords = {
        '검정': ['검정', '블랙', 'black', '흑색', '까만', '흑', '다크', 'dark', 'charcoal', '차콜', 'jet', '젯', 'ebony', '에보니', 'obsidian', '옵시디언', 'coal', '석탄', 'raven', '까마귀', 'soot', '그을음'],
        
        '흰색': ['흰색', '화이트', 'white', '백색', '하얀', '백', 'ivory', '아이보리', 'cream', '크림', 'pearl', '진주', 'snow', '눈', 'vanilla', '바닐라', 'bone', '뼈', 'linen', '리넨', 'cotton', '코튼', 'milk', '우유', 'eggshell', '달걀껍질', 'chalk', '분필'],
        
        '빨강': ['빨강', '레드', 'red', '적색', '빨간', '적', 'crimson', '크림슨', 'scarlet', '스칼렛', 'cherry', '체리', 'rose', '로즈', 'wine', '와인', 'burgundy', '버건디', 'maroon', '마룬', 'brick', '브릭', 'rust', '러스트', 'cardinal', '카디널', 'fire', '파이어', 'blood', '블러드', 'tomato', '토마토', 'strawberry', '딸기', 'ruby', '루비'],
        
        '파랑': ['파랑', '블루', 'blue', '네이비', 'navy', '청색', '남색', '하늘색', 'sky', 'skyblue', 'lightblue', 'darkblue', 'royal', 'royalblue', 'cobalt', 'azure', 'cyan', 'teal', 'turquoise', 'aqua', 'steel', 'steelblue', 'powder', 'powderblue', 'cornflower', 'midnight', 'midnightblue', 'slate', 'slateblue', 'dodger', 'dodgerblue', 'deep', 'deepblue', 'electric', 'electricblue', 'sapphire', 'indigo', '인디고', '아쿠아', '시안', '틸', '터키석', '사파이어', '코발트', '하늘', '스카이', '로얄', '미드나잇', '슬레이트', '파우더', '스틸'],
        
        '노랑': ['노랑', '옐로우', 'yellow', '황색', '노란', '황', 'gold', '골드', 'lemon', '레몬', 'banana', '바나나', 'corn', '옥수수', 'mustard', '머스타드', 'amber', '앰버', 'honey', '꿀', 'butter', '버터', 'cream', '크림', 'sand', '모래', 'wheat', '밀', 'champagne', '샴페인', 'canary', '카나리아', 'sunshine', '햇빛', 'dandelion', '민들레'],
        
        '초록': ['초록', '그린', 'green', '녹색', '초록색', '녹', 'forest', '포레스트', 'emerald', '에메랄드', 'lime', '라임', 'mint', '민트', 'olive', '올리브', 'sage', '세이지', 'jade', '제이드', 'kelly', '켈리', 'hunter', '헌터', 'grass', '잔디', 'leaf', '잎', 'moss', '이끼', 'pine', '소나무', 'seafoam', '시폼', 'spring', '봄', 'apple', '사과', 'chartreuse', '샤르트뢰즈'],
        
        '보라': ['보라', '퍼플', 'purple', '자주', '자색', '보랏빛', 'violet', '바이올렛', 'lavender', '라벤더', 'plum', '자두', 'grape', '포도', 'eggplant', '가지', 'orchid', '난초', 'lilac', '라일락', 'magenta', '마젠타', 'fuchsia', '푸시아', 'amethyst', '자수정', 'royal', '로얄퍼플', 'deep', '딥퍼플', 'dark', '다크퍼플', 'light', '라이트퍼플', 'mauve', '모브', 'periwinkle', '페리윙클'],
        
        '주황': ['주황', '오렌지', 'orange', '주황색', '오렌지색', 'tangerine', '탠저린', 'peach', '피치', 'coral', '코랄', 'salmon', '샐몬', 'apricot', '살구', 'mandarin', '만다린', 'pumpkin', '호박', 'carrot', '당근', 'rust', '러스트', 'burnt', '번트', 'terra', '테라', 'cinnamon', '시나몬', 'copper', '구리', 'bronze', '브론즈', 'autumn', '가을', 'sunset', '석양'],
        
        '분홍': ['분홍', '핑크', 'pink', '분홍색', '핑크색', 'rose', '로즈', 'blush', '블러시', 'cherry', '체리', 'salmon', '샐몬', 'coral', '코랄', 'peach', '피치', 'baby', '베이비', 'hot', '핫핑크', 'magenta', '마젠타', 'fuchsia', '푸시아', 'bubblegum', '버블검', 'cotton', '솜사탕', 'flamingo', '플라밍고', 'carnation', '카네이션', 'dusty', '더스티', 'pale', '페일', 'light', '라이트'],
        
        '회색': ['회색', '그레이', 'gray', 'grey', '회', '회색빛', 'silver', '실버', 'charcoal', '차콜', 'slate', '슬레이트', 'ash', '애시', 'smoke', '스모크', 'steel', '스틸', 'pewter', '퓨터', 'graphite', '그래파이트', 'storm', '스톰', 'fog', '포그', 'mist', '미스트', 'cement', '시멘트', 'concrete', '콘크리트', 'stone', '스톤', 'gunmetal', '건메탈', 'platinum', '플래티넘'],
        
        '갈색': ['갈색', '브라운', 'brown', '갈', '갈색빛', 'chocolate', '초콜릿', 'coffee', '커피', 'tan', '탄', 'beige', '베이지', 'khaki', '카키', 'camel', '카멜', 'chestnut', '밤색', 'mahogany', '마호가니', 'walnut', '호두', 'cinnamon', '시나몬', 'bronze', '브론즈', 'copper', '구리', 'rust', '러스트', 'amber', '앰버', 'honey', '꿀', 'sand', '모래', 'earth', '어스', 'mud', '머드', 'wood', '우드'],
        
        '베이지': ['베이지', 'beige', '연갈색', 'cream', '크림', 'ivory', '아이보리', 'tan', '탄', 'sand', '모래', 'wheat', '밀', 'oatmeal', '오트밀', 'linen', '리넨', 'vanilla', '바닐라', 'champagne', '샴페인', 'buff', '버프', 'nude', '누드', 'natural', '내추럴', 'ecru', '에크루', 'bone', '뼈', 'pearl', '진주', 'oyster', '굴', 'parchment', '양피지']
    }
    
    # 선호 색상에 해당하는 키워드 찾기
    target_keywords = []
    for color_name, keywords in color_keywords.items():
        if any(keyword in preferred_color.lower() for keyword in keywords):
            target_keywords.extend(keywords)
            break
    
    if not target_keywords:
        return products
    
    # 색상 필터링 (더 정확한 단어 단위 매칭)
    filtered_products = []
    for product in products:
        product_color = product.get('색상', '').lower()
        
        # 색상 문자열을 단어로 분리 (쉼표, 공백, 슬래시 등으로 구분)
        color_words = []
        for separator in [',', ' ', '/', '\\', '|', '&', '+']:
            if separator in product_color:
                color_words.extend([word.strip() for word in product_color.split(separator)])
        
        # 분리된 단어가 없으면 전체 문자열을 하나의 단어로 처리
        if not color_words:
            color_words = [product_color]
        
        # 중복 제거 및 빈 문자열 제거
        color_words = list(set([word for word in color_words if word]))
        
        # 키워드 매칭 확인
        is_matched = False
        for color_word in color_words:
            if any(keyword in color_word or color_word in keyword for keyword in target_keywords):
                is_matched = True
                break
        
        if is_matched:
            filtered_products.append(product)
    
    return filtered_products if filtered_products else products


def get_product_by_id(db: Session, product_id: int) -> Optional[Dict]:
    """상품 ID로 상품 정보를 조회합니다."""
    try:
        # 상품 데이터를 조회하는 쿼리 (실제 테이블 구조에 맞게 수정 필요)
        # 여기서는 예시로 빈 딕셔너리를 반환합니다.
        # 실제 구현 시에는 상품 테이블에서 조회해야 합니다.
        
        # 임시로 상품 데이터를 반환 (실제 구현 시 수정 필요)
        return {
            "상품코드": product_id,
            "상품명": f"상품 {product_id}",
            "브랜드": "브랜드명",
            "가격": 50000,
            "이미지URL": "",
            "상품링크": ""
        }
    except Exception as e:
        print(f"상품 조회 중 오류: {e}")
        return None


