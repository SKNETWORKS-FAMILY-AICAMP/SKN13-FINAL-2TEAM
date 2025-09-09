import boto3
import pandas as pd
import numpy as np
import os
from typing import List, Dict, Optional
from botocore.exceptions import NoCredentialsError, ClientError
import json
import io
from utils.safe_utils import safe_lower, safe_str

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
        return ""

    def load_product_data(self, file_key: str, use_cache: bool = True) -> List[Dict]:
        """제품 데이터를 S3에서 로드하고 가공하여 반환 (중앙 조회 테이블 생성 포함)"""
        from cache_manager import cache_manager
        from data_store import product_lookup_table

        # 캐시 키 버전을 v9로 업데이트하여 강제로 캐시 무효화
        cache_identifier = f"s3_products_{self.bucket_name}_{file_key}_v9"
        
        if use_cache:
            cached_data = cache_manager.get(cache_identifier)
            if cached_data:
                print(f"✅ 캐시(v9)에서 '{cache_identifier}' 데이터를 가져왔습니다.")
                # 캐시된 데이터로 조회 테이블 채우기
                if not product_lookup_table:
                    for product in cached_data:
                        if product_id := product.get("상품코드"):
                            product_lookup_table[str(product_id)] = product
                    print(f"✅ 캐시된 데이터로 중앙 조회 테이블을 생성했습니다: {len(product_lookup_table)}개 항목")
                return cached_data
        
        print(f"ℹ️ 캐시에 데이터가 없어 S3에서 직접 로드합니다: {file_key}")
        try:
            df = self.load_csv_from_s3(file_key)
            if df.empty:
                return []
            
            df = df.replace({np.nan: None})
            raw_data = df.to_dict("records")
            
            clothing_data = []
            for idx, item in enumerate(raw_data):
                price_val = item.get("원가")
                price = int(price_val) if isinstance(price_val, (int, float)) and pd.notna(price_val) else 0
                image_url = self.fix_image_url(item.get("이미지URL") or "")

                product_code = str(item.get("상품코드")) if item.get("상품코드") else f"generated_id_{idx}"

                mapped_item = {
                    "사진": image_url,
                    "상품명": item.get("상품명") or "상품 정보 없음",
                    "한글브랜드명": item.get("한글브랜드명") or "브랜드 정보 없음",
                    "가격": price,
                    "상품코드": product_code,
                    "대분류": item.get("대분류", ""),
                    "소분류": item.get("소분류", ""),
                    "원가": price,
                    "할인가": item.get("할인가"),
                    "성별": item.get("성별", "공용"),
                    "이미지URL": image_url,
                    "소재": item.get("소재", ""),
                    "색상": item.get("색상", ""),
                    "좋아요수": item.get("좋아요수", 0),
                    "상품링크": item.get("상품링크", ""),
                    "영어브랜드명": item.get("영어브랜드명", ""),
                    "사이트명": item.get("사이트명", ""),
                }
                clothing_data.append(mapped_item)
            
            print(f"✅ 제품 데이터 가공 완료: {len(clothing_data)}개 상품")

            # 중앙 조회 테이블 생성
            product_lookup_table.clear() # 기존 데이터 초기화
            for product in clothing_data:
                if product_id := product.get("상품코드"):
                    product_lookup_table[str(product_id)] = product
            print(f"✅ 중앙 조회 테이블 생성 완료: {len(product_lookup_table)}개 항목")

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
