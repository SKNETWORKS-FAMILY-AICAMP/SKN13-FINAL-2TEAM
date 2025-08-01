
import pandas as pd
import random

try:
    # CSV 파일에서 데이터 읽기
    df = pd.read_csv("products.csv")

    # "대표이미지URL"이 존재하고, 문자열 타입인지 확인 후 "https://" 추가
    if "대표이미지URL" in df.columns and df["대표이미지URL"].dtype == 'object':
        # pd.NA가 아닌 실제 문자열 값에만 적용
        df["대표이미지URL"] = df["대표이미지URL"].str.strip().apply(lambda x: f"https:{x}" if pd.notna(x) and not x.startswith('http') else x)

    # 데이터프레임을 딕셔너리 리스트로 변환
    all_products = df.to_dict("records")
    print("Product data loaded and processed successfully.")

except FileNotFoundError:
    print("Error: products.csv not found.")
    all_products = []
except Exception as e:
    print(f"An error occurred while processing products.csv: {e}")
    all_products = []

def get_all_products():
    """모든 상품 리스트를 반환합니다."""
    return all_products

def get_random_products(count: int):
    """지정된 개수만큼 무작위 상품 리스트를 반환합니다."""
    if len(all_products) >= count:
        return random.sample(all_products, count)
    return all_products
