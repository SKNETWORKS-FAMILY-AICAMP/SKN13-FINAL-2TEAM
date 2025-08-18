import boto3
import pandas as pd
import numpy as np
import os
from typing import List, Dict, Optional
from botocore.exceptions import NoCredentialsError, ClientError
import json
import io

class S3DataLoader:
    """S3에서 데이터를 로드하는 클래스"""
    
    def __init__(self):
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY') 
        self.aws_region = os.getenv('AWS_REGION', 'ap-northeast-2')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
            print(f"✅ S3 클라이언트 초기화 완료: {self.bucket_name}")
        except Exception as e:
            print(f"❌ S3 클라이언트 초기화 실패: {e}")
            self.s3_client = None
    
    def load_csv_from_s3(self, file_key: str) -> pd.DataFrame:
        """S3에서 CSV 파일을 읽어서 DataFrame으로 반환"""
        try:
            if not self.s3_client:
                raise Exception("S3 클라이언트가 초기화되지 않았습니다.")
            
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            csv_content = response['Body'].read()
            df = pd.read_csv(io.StringIO(csv_content.decode('utf-8')))
            print(f"✅ S3 데이터 로드 완료: {len(df)}행, {len(df.columns)}열")
            return df
            
        except Exception as e:
            print(f"❌ S3 파일 로드 오류: {e}")
            return pd.DataFrame()

    def fix_image_url(self, url: str) -> str:
        """이미지 URL을 검증하고 필요시 수정합니다."""
        if pd.isna(url) or not isinstance(url, str):
            return ""

        url = url.strip()
        if not url:
            return ""

        # 이미 올바른 http/https URL인 경우 그대로 사용
        if url.startswith(("http://", "https://")):
            return url
        
        # 스킴 없는 URL인 경우 https 추가
        if url.startswith("//"):
            return f"https:{url}"
        
        # 상대 경로인 경우 기본 도메인 추가
        if url.startswith("/"):
            return f"https://image.msscdn.net{url}"
        
        # 그 외의 경우 빈 문자열 반환
        print(f"⚠️ [URL 경고] 인식할 수 없는 URL 형식: '{url}'")
        return ""



    def load_product_data(self, file_key: str, use_cache: bool = True) -> List[Dict]:
        """제품 데이터를 S3에서 로드하고 가공하여 반환 (캐싱 지원 및 상세 로깅)"""
        from cache_manager import cache_manager
        # 캐시 식별자에 버전(_v5)을 추가하여 이전 캐시를 무효화합니다.
        cache_identifier = f"s3_products_{self.bucket_name}_{file_key}_v5"
        
        if use_cache:
            cached_data = cache_manager.get(cache_identifier)
            if cached_data:
                print(f"✅ 캐시(v5)에서 '{cache_identifier}' 데이터를 가져왔습니다.")
                return cached_data
        
        print(f"ℹ️ 캐시에 데이터가 없어 S3에서 직접 로드합니다: {file_key}")
        try:
            df = self.load_csv_from_s3(file_key)
            if df.empty:
                return []
            
            df = df.replace({np.nan: None})
            
            # 새로운 컬럼 구조에 맞는 이미지 URL 컬럼 찾기
            image_col = next((col for col in ['이미지URL', '사진', '대표이미지URL'] if col in df.columns), None)

            if image_col:
                print(f"🖼️ '{image_col}' 컬럼의 이미지 URL을 처리합니다...")
                df['fixed_image_url'] = df[image_col].apply(self.fix_image_url)
            else:
                print("⚠️ 이미지 URL 컬럼('이미지URL', '사진' 또는 '대표이미지URL')을 찾을 수 없습니다.")
                df['fixed_image_url'] = ""

            raw_data = df.to_dict("records")
            
            clothing_data = []
            import hashlib
            for item in raw_data:
                # 가격 처리 - 할인가 우선, 없으면 원가 사용
                discount_price = item.get("할인가", 0)
                original_price = item.get("원가", 0)
                
                # 숫자가 아닌 경우 0으로 처리
                if not isinstance(discount_price, (int, float)) or discount_price == 0:
                    price = original_price if isinstance(original_price, (int, float)) else 0
                else:
                    price = discount_price
                
                fixed_img = item.get('fixed_image_url', '')
                # 제품 식별자 결정 - 새로운 컬럼명 사용
                product_id = (
                    item.get('상품코드') or item.get('상품ID') or item.get('제품ID') or item.get('id') or item.get('ID')
                )
                if not product_id:
                    key_src = f"{item.get('상품명', '')}|{item.get('한글브랜드명', '')}|{price}"
                    product_id = hashlib.md5(key_src.encode('utf-8')).hexdigest()[:16]
                
                # 분류/성별/평점 등 사전 계산하여 이후 요청시 재계산 방지
                name_lower = str(item.get("상품명", "")).lower()
                
                # 의류 타입/소분류
                if any(w in name_lower for w in ['티셔츠', 't-shirt', 'tshirt', '티 ', 'shirt']):
                    clothing_type, subcat = '상의', '티셔츠'
                elif any(w in name_lower for w in ['맨투맨', '후드', 'sweatshirt', 'hoodie']):
                    clothing_type, subcat = '상의', '맨투맨/후드'
                elif any(w in name_lower for w in ['셔츠', 'blouse', '블라우스']):
                    clothing_type, subcat = '상의', '셔츠/블라우스'
                elif any(w in name_lower for w in ['니트', 'knit', '스웨터']):
                    clothing_type, subcat = '상의', '니트'
                elif any(w in name_lower for w in ['민소매', '탑', 'top', '크롭']):
                    clothing_type, subcat = '상의', '민소매'
                elif any(w in name_lower for w in ['바지', '팬츠', 'pants', 'jeans', '청바지']):
                    clothing_type = '하의'
                    if any(w in name_lower for w in ['청바지', 'jeans']):
                        subcat = '청바지'
                    elif any(w in name_lower for w in ['반바지', 'shorts']):
                        subcat = '반바지'
                    elif any(w in name_lower for w in ['레깅스', 'leggings']):
                        subcat = '레깅스'
                    elif any(w in name_lower for w in ['조거', 'jogger']):
                        subcat = '조거팬츠'
                    else:
                        subcat = '팬츠'
                elif any(w in name_lower for w in ['스커트', 'skirt']):
                    clothing_type = '스커트'
                    if any(w in name_lower for w in ['미니', 'mini']):
                        subcat = '미니스커트'
                    elif any(w in name_lower for w in ['미디', 'midi']):
                        subcat = '미디스커트'
                    elif any(w in name_lower for w in ['맥시', 'maxi']):
                        subcat = '맥시스커트'
                    elif any(w in name_lower for w in ['플리츠', 'pleated']):
                        subcat = '플리츠스커트'
                    elif any(w in name_lower for w in ['a라인', 'a-line']):
                        subcat = 'A라인스커트'
                    else:
                        subcat = '스커트'
                else:
                    clothing_type, subcat = '상의', '기타'

                # 성별 추정
                if any(w in name_lower for w in ['우먼', 'women', '여성', 'lady', '여자']):
                    gender = '여성'
                elif any(w in name_lower for w in ['남성', 'men', 'man', '남자']):
                    gender = '남성'
                elif any(w in name_lower for w in ['unisex', '유니섹스']):
                    gender = '유니섹스'
                else:
                    gender = '여성'

                # 평점(의사 랜덤 고정)
                import hashlib
                hash_object = hashlib.md5(name_lower.encode())
                hash_int = int(hash_object.hexdigest()[:8], 16)
                rating = 1.0 + (hash_int % 400) / 100.0

                mapped_item = {
                    # 새로운 컬럼 구조에 맞게 매핑
                    "상품코드": str(product_id),
                    "상품명": item.get("상품명", ""),
                    "한글브랜드명": item.get("한글브랜드명", ""),
                    "대분류": item.get("대분류", ""),
                    "소분류": item.get("소분류", ""),
                    "원가": int(original_price),
                    "할인가": int(discount_price),
                    "성별": item.get("성별", gender),
                    "이미지URL": fixed_img,
                    "소재": item.get("소재", ""),
                    "색상": item.get("색상", ""),
                    "좋아요수": item.get("좋아요수", 0),
                    "상품링크": item.get("상품링크", ""),
                    "영어브랜드명": item.get("영어브랜드명", ""),
                    
                    # 호환성을 위한 기존 필드들 (하위 호환성)
                    "브랜드": item.get("한글브랜드명", ""),
                    "가격": int(price),
                    "사진": fixed_img,
                    "상품ID": str(product_id),
                    "대표이미지URL": fixed_img,
                    
                    # 사전 계산 필드
                    "processed_price": int(price),
                    "의류타입": clothing_type,
                    "평점": round(rating, 1),
                }
                clothing_data.append(mapped_item)
            
            print(f"✅ 제품 데이터 가공 완료: {len(clothing_data)}개 상품")
            
            if use_cache and clothing_data:
                cache_manager.set(cache_identifier, clothing_data)
                print(f"💾 가공된 데이터를 캐시에 저장했습니다: '{cache_identifier}'")
            
            return clothing_data
            
        except Exception as e:
            print(f"❌ 제품 데이터 처리 중 심각한 오류 발생: {e}")
            return []

s3_loader = S3DataLoader()

def get_product_data_from_s3(file_key: str) -> List[Dict]:
    return s3_loader.load_product_data(file_key)
