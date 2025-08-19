from typing import Optional

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
        '검정': ['검정', '블랙', 'black'],
        '흰색': ['흰색', '화이트', 'white'],
        '빨강': ['빨강', '레드', 'red'],
        '파랑': ['파랑', '블루', 'blue'],
        '노랑': ['노랑', '옐로우', 'yellow'],
        '초록': ['초록', '그린', 'green'],
        '보라': ['보라', '퍼플', 'purple'],
        '주황': ['주황', '오렌지', 'orange'],
        '분홍': ['분홍', '핑크', 'pink'],
        '회색': ['회색', '그레이', 'gray', 'grey'],
        '갈색': ['갈색', '브라운', 'brown'],
        '베이지': ['베이지', 'beige'],
        '네이비': ['네이비', 'navy'],
        '카키': ['카키', 'khaki'],
        '민트': ['민트', 'mint'],
        '코랄': ['코랄', 'coral'],
        '골드': ['골드', 'gold'],
        '실버': ['실버', 'silver']
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


