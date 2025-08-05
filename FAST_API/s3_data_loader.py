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

    def fix_image_url(self, url):
        """이미지 URL을 올바른 형식으로 수정합니다."""
        if pd.isna(url) or url is None:
            return ""
        url = str(url).strip()
        
        # //로 시작하는 경우 (e.g., //product-image.wconcept.co.kr/...)
        if url.startswith("//"):
            return f"https:{url}"
        
        # https:/ 로 잘못 시작하는 경우
        if url.startswith("https:/") and not url.startswith("https://"):
            return url.replace("https:/", "https://", 1)

        # Musinsa 관련 상대 경로 처리
        if url.startswith("images/goods_img/") or url.startswith("/images/goods_img/"):
            return f"https://image.msscdn.net/thumbnails/{url.lstrip('/')}"

        return url

    def load_product_data(self, file_key: str, use_cache: bool = True) -> List[Dict]:
        """제품 데이터를 S3에서 로드하고 가공하여 반환 (캐싱 지원)"""
        from cache_manager import cache_manager
        cache_identifier = f"s3_products_{self.bucket_name}_{file_key}"
        
        if use_cache:
            cached_data = cache_manager.get(cache_identifier)
            if cached_data:
                return cached_data
        
        try:
            df = self.load_csv_from_s3(file_key)
            if df.empty:
                return []
            
            df = df.replace({np.nan: None})
            
            # 이미지 URL 컬럼명을 유연하게 찾기 ('사진' 또는 '대표이미지URL')
            image_col = None
            if '사진' in df.columns:
                image_col = '사진'
            elif '대표이미지URL' in df.columns:
                image_col = '대표이미지URL'

            if image_col:
                df[image_col] = df[image_col].apply(self.fix_image_url)
            
            raw_data = df.to_dict("records")
            
            clothing_data = []
            for item in raw_data:
                # 이미지 URL을 '사진' 키로 통일
                image_url = item.get('사진', item.get('대표이미지URL', ''))
                
                mapped_item = {
                    "상품명": item.get("제품이름", item.get("상품명", "")) or "",
                    "브랜드": item.get("브랜드", "") or "",
                    "가격": item.get("가격", 0) or 0,
                    "사진": image_url or "",
                    # 다른 필드들도 필요에 따라 추가
                }
                clothing_data.append(mapped_item)
            
            print(f"✅ 제품 데이터 가공 완료: {len(clothing_data)}개 상품")
            
            if use_cache and clothing_data:
                cache_manager.set(cache_identifier, clothing_data)
            
            return clothing_data
            
        except Exception as e:
            print(f"❌ 제품 데이터 처리 실패: {e}")
            return []

s3_loader = S3DataLoader()

def get_product_data_from_s3(file_key: str) -> List[Dict]:
    return s3_loader.load_product_data(file_key)
