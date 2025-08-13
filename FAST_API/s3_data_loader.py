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
        """이미지 URL을 정리하여 반환합니다."""
        if pd.isna(url) or not isinstance(url, str):
            return ""

        url = url.strip()
        if not url:
            return ""

        # 스킴 없는 URL (//로 시작하는 경우)에 https: 추가
        if url.startswith("//"):
            url = f"https:{url}"
        
        # 최종 검증: http/https 스킴이 없으면 빈 문자열 반환
        if not url.startswith(("http://", "https://")):
            print(f"⚠️ [URL 경고] 유효하지 않은 URL: '{url}'")
            return ""

        return url



    def load_product_data(self, file_key: str, use_cache: bool = True) -> List[Dict]:
        """제품 데이터를 S3에서 로드하고 가공하여 반환 (캐싱 지원)"""
        from cache_manager import cache_manager
        # 캐시 식별자에 버전(_v6)을 추가하여 이전 캐시를 무효화합니다.
        cache_identifier = f"s3_products_{self.bucket_name}_{file_key}_v6"
        
        if use_cache:
            cached_data = cache_manager.get(cache_identifier)
            if cached_data:
                print(f"✅ 캐시(v6)에서 '{cache_identifier}' 데이터를 가져왔습니다.")
                return cached_data
        
        print(f"ℹ️ 캐시에 데이터가 없어 S3에서 직접 로드합니다: {file_key}")
        try:
            df = self.load_csv_from_s3(file_key)
            if df.empty:
                return []
            
            df = df.replace({np.nan: None})
            
            # 새로운 컬럼명에 맞춰 이미지 URL 처리
            image_col = next((col for col in ['이미지 url', '대표이미지URL', '사진'] if col in df.columns), None)

            if image_col:
                print(f"🖼️ '{image_col}' 컬럼의 이미지 URL을 처리합니다...")
                df['fixed_image_url'] = df[image_col].apply(self.fix_image_url)
            else:
                print("⚠️ 이미지 URL 컬럼('이미지 url', '대표이미지URL', '사진')을 찾을 수 없습니다.")
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
                
                # 제품 식별자 결정 - 상품코드 우선
                product_id = (
                    item.get('상품코드') or item.get('상품ID') or item.get('제품ID') or item.get('id') or item.get('ID')
                )
                if not product_id:
                    key_src = f"{item.get('제품이름', '')}|{item.get('브랜드명', item.get('브랜드', ''))}|{price}|{item.get('색상', '')}|{item.get('사이즈', '')}"
                    product_id = hashlib.md5(key_src.encode('utf-8')).hexdigest()[:16]

                mapped_item = {
                    "상품코드": str(product_id),
                    "제품이름": item.get("제품이름", ""),
                    "브랜드명": item.get("브랜드명", item.get("브랜드", "")),
                    "대분류": item.get("대분류", ""),
                    "소분류": item.get("소분류", ""),
                    "원가": int(original_price) if isinstance(original_price, (int, float)) else 0,
                    "할인가": int(discount_price) if isinstance(discount_price, (int, float)) else 0,
                    "성별": item.get("성별", ""),
                    "이미지 url": fixed_img,
                    "소재": item.get("제품소재", ""),
                    "색상": item.get("색상", ""),
                    "좋아요 수": item.get("좋아요 수", 0),
                    "상품링크": item.get("상품링크", ""),
                    # 기존 호환성을 위한 필드들
                    "브랜드": item.get("브랜드명", item.get("브랜드", "")),
                    "가격": int(price),
                    "사진": fixed_img,
                    "상품ID": str(product_id),
                    "대표이미지URL": fixed_img,
                    "processed_price": int(price),
                }
                clothing_data.append(mapped_item)
                print(f"DEBUG: Processed item - Product ID: {mapped_item['상품ID']}, Name: {mapped_item['제품이름']}, Color: {mapped_item.get('색상', 'N/A')}, Size: {mapped_item.get('사이즈', 'N/A')}")
            
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
