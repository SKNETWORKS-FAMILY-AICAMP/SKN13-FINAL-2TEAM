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
        """
        이미지 URL을 올바른 웹 접근 가능 형식으로 수정하고, 문제가 될 수 있는 URL을 로깅합니다.
        """
        if pd.isna(url) or not isinstance(url, str) or not url.strip():
            return ""

        original_url = url.strip()
        fixed_url = original_url

        # Case 1: "https://images/goods_img/..." 와 같이 잘못된 도메인이 포함된 경우
        if "images/goods_img/" in fixed_url:
            # "images/goods_img/" 이후의 경로만 추출
            path_part = fixed_url.split("images/goods_img/")[-1]
            fixed_url = f"https://image.msscdn.net/thumbnails/images/goods_img/{path_part}"

        # Case 2: "//"로 시작하는 경우
        elif fixed_url.startswith("//"):
            fixed_url = f"https:{fixed_url}"
        
        # Case 3: "https:/" 와 같이 오타가 있는 경우
        elif fixed_url.startswith("https:/") and not fixed_url.startswith("https://"):
            fixed_url = fixed_url.replace("https:/", "https://", 1)

        # 최종 URL이 http로 시작하지 않으면 경고 로깅 (수정 후에도 여전히 문제인 경우)
        if not fixed_url.startswith(("http://", "https://")):
            print(f"⚠️ [URL 경고] 최종 URL이 유효한 프로토콜로 시작하지 않습니다: '{fixed_url}' (원본: '{original_url}')")

        # 원본과 수정된 URL이 다른 경우 로깅
        if original_url != fixed_url:
            print(f"🔧 [URL 수정] 원본: '{original_url}' -> 수정: '{fixed_url}'")
            
        return fixed_url

    def load_product_data(self, file_key: str, use_cache: bool = True) -> List[Dict]:
        """제품 데이터를 S3에서 로드하고 가공하여 반환 (캐싱 지원 및 상세 로깅)"""
        from cache_manager import cache_manager
        # 캐시 식별자에 버전(_v2)을 추가하여 이전 캐시를 무효화합니다.
        cache_identifier = f"s3_products_{self.bucket_name}_{file_key}_v2"
        
        if use_cache:
            cached_data = cache_manager.get(cache_identifier)
            if cached_data:
                print(f"✅ 캐시(v2)에서 '{cache_identifier}' 데이터를 가져왔습니다.")
                return cached_data
        
        print(f"ℹ️ 캐시에 데이터가 없어 S3에서 직접 로드합니다: {file_key}")
        try:
            df = self.load_csv_from_s3(file_key)
            if df.empty:
                return []
            
            df = df.replace({np.nan: None})
            
            image_col = next((col for col in ['사진', '대표이미지URL'] if col in df.columns), None)

            if image_col:
                print(f"🖼️ '{image_col}' 컬럼의 이미지 URL을 처리합니다...")
                df['fixed_image_url'] = df[image_col].apply(self.fix_image_url)
            else:
                print("⚠️ 이미지 URL 컬럼('사진' 또는 '대표이미지URL')을 찾을 수 없습니다.")
                df['fixed_image_url'] = ""

            raw_data = df.to_dict("records")
            
            clothing_data = []
            for item in raw_data:
                mapped_item = {
                    "상품명": item.get("제품이름", item.get("상품명", "")),
                    "브랜드": item.get("브랜드", ""),
                    "가격": item.get("가격", 0),
                    "사진": item.get('fixed_image_url', ''),
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
