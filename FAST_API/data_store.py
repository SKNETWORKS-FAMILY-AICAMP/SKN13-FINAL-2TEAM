from typing import List, Dict

# S3 또는 다른 소스에서 로드된 원본 제품 데이터를 저장하는 중앙 저장소입니다.
clothing_data: List[Dict] = []

# 애플리케이션 시작 시 한 번 가공된 제품 데이터를 저장하는 캐시 저장소입니다.
processed_clothing_data: List[Dict] = []