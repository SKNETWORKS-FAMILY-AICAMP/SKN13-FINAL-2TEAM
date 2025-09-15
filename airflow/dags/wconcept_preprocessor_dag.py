from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
import pandas as pd
import re
import os
from typing import Dict, List, Optional

# DAG 기본 설정
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'catchup': False
}

# DAG 정의
dag = DAG(
    'wconcept_preprocessor_csv',
    default_args=default_args,
    description='W컨셉 상품 데이터 전처리 파이프라인 DAG (CSV 기반)',
    schedule_interval=None,
    max_active_runs=1,
    tags=['preprocessing', 'wconcept', 'ecommerce', 'data-cleaning', 'csv-based']
)

# 파일 경로 설정
BASE_PATH = "/home/tjddml/airflow/dags/wconcept"
INPUT_FILE = "../w/parsed_products.csv"
BRANDS_FILE = "/home/tjddml/airflow/dags/brands.csv"
TEMP_FILES = {
    'step1': f"{BASE_PATH}/tmp_step1_loaded.csv",
    'step2': f"{BASE_PATH}/tmp_step2_cleaned.csv", 
    'step3': f"{BASE_PATH}/tmp_step3_colors.csv",
    'step4': f"{BASE_PATH}/tmp_step4_filtered.csv",
    'step5': f"{BASE_PATH}/tmp_step5_brands.csv",
    'step6': f"{BASE_PATH}/tmp_step6_brand_filtered.csv",
    'step7': f"{BASE_PATH}/tmp_step7_categories.csv"
}
OUTPUT_FILE = f"{BASE_PATH}/processed_products.csv"

class WconceptPreprocessor:
    def __init__(self):
        """W컨셉 전처리 클래스"""
        # 대분류-소분류 매핑 정의
        self.category_mapping = {
            '상의': ['후드티', '셔츠/블라우스', '긴소매', '반소매', '피케/카라', '니트/스웨터', '슬리브리스'],
            '바지': ['데님팬츠', '트레이닝/조거팬츠', '코튼팬츠', '슈트팬츠/슬랙스', '숏팬츠', '카고팬츠'],
            '원피스': ['미니원피스', '미디원피스', '맥시원피스'],
            '스커트': ['미니스커트', '미디스커트', '롱스커트']
        }

# 태스크 함수들 (각 태스크는 CSV 파일을 읽고 처리 후 다음 CSV 파일로 저장)

def load_data_task(**context):
    """1단계: 초기 데이터 로드 및 브랜드 매핑 준비"""
    print("📂 1단계: 데이터 로드 중...")
    
    # 원본 데이터 로드
    df = pd.read_csv(INPUT_FILE, encoding='utf-8-sig')
    print(f"✅ 원본 데이터 로드 완료: {len(df)}행")
    
    # 브랜드 매핑 로드 및 확인
    brands_df = pd.read_csv(BRANDS_FILE, encoding='utf-8-sig')
    brands_mapping = dict(zip(brands_df['영어브랜드명'], brands_df['한글브랜드명']))
    print(f"✅ 브랜드 매핑 로드 완료: {len(brands_mapping)}개")
    
    # 1단계 결과 저장
    df.to_csv(TEMP_FILES['step1'], index=False, encoding='utf-8-sig')
    print(f"💾 1단계 결과 저장: {TEMP_FILES['step1']}")
    
    return f"데이터 로드 완료 - {len(df)}행"

def clean_product_names_task(**context):
    """2단계: 상품명 전처리"""
    print("🧹 2단계: 상품명 전처리 중...")
    
    # 이전 단계 결과 로드
    df = pd.read_csv(TEMP_FILES['step1'], encoding='utf-8-sig')
    print(f"📂 이전 단계 데이터 로드: {len(df)}행")
    
    def clean_name(name):
        if pd.isna(name):
            return name
        
        # 괄호와 대괄호 안 내용 제거
        name = re.sub(r'\([^)]*\)', '', str(name))
        name = re.sub(r'\[[^\]]*\]', '', name)
        
        # 특수문자 정리
        name = re.sub(r'[^\w\s가-힣]', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    # 상품명 정리
    df['상품명'] = df['상품명'].apply(clean_name)
    print("✅ 상품명 전처리 완료")
    
    # 2단계 결과 저장
    df.to_csv(TEMP_FILES['step2'], index=False, encoding='utf-8-sig')
    print(f"💾 2단계 결과 저장: {TEMP_FILES['step2']}")
    
    return f"상품명 전처리 완료 - {len(df)}행"

def extract_colors_task(**context):
    """3단계: 상품명에서 색상 정보 추출"""
    print("🎨 3단계: 상품명에서 색상 추출 중...")
    
    # 이전 단계 결과 로드
    df = pd.read_csv(TEMP_FILES['step2'], encoding='utf-8-sig')
    print(f"📂 이전 단계 데이터 로드: {len(df)}행")
    
    # 색상 패턴 정의
    color_patterns = {
        'black': [r'블랙', r'black', r'\bbk\b', r'흑'],
        'white': [r'화이트', r'white', r'\bwh\b', r'백색', r'오프화이트'],
        'ivory': [r'아이보리', r'ivory', r'\biv\b'],
        'beige': [r'베이지', r'beige', r'\bbg\b'],
        'brown': [r'브라운', r'brown', r'\bbr\b', r'카키', r'차콜'],
        'navy': [r'네이비', r'navy', r'\bnv\b'],
        'blue': [r'블루', r'blue', r'\bbl\b', r'스카이블루'],
        'denim': [r'데님', r'denim', r'인디고'],
        'green': [r'그린', r'green', r'\bgr\b'],
        'grey': [r'그레이', r'grey', r'gray', r'\bgy\b'],
        'red': [r'레드', r'red', r'\brd\b', r'와인'],
        'orange': [r'오렌지', r'orange', r'\borg\b'],
        'yellow': [r'옐로우', r'yellow', r'\bye\b'],
        'pink': [r'핑크', r'pink', r'\bpk\b', r'로즈'],
        'purple': [r'퍼플', r'purple', r'\bpp\b', r'보라'],
        'mint': [r'민트', r'mint'],
        'cream': [r'크림', r'cream'],
        'gold': [r'골드', r'gold'],
        'silver': [r'실버', r'silver'],
        'multi': [r'멀티', r'multi']
    }
    
    def extract_color(name):
        if pd.isna(name):
            return None
        
        name = str(name).lower()
        found_colors = []
        
        for color, patterns in color_patterns.items():
            for pattern in patterns:
                if re.search(pattern, name, re.IGNORECASE):
                    found_colors.append(color)
                    break
        
        return ', '.join(found_colors) if found_colors else None
    
    # 색상 추출
    df['색상_추출'] = df['상품명'].apply(extract_color)
    
    # 기존 색상과 추출된 색상 결합
    df['색상'] = df['색상'].fillna('')
    df['색상_추출'] = df['색상_추출'].fillna('')
    
    # 색상이 비어있으면 추출된 색상 사용
    mask = (df['색상'].str.strip() == '') & (df['색상_추출'].str.strip() != '')
    df.loc[mask, '색상'] = df.loc[mask, '색상_추출']
    
    # 색상_추출 컬럼 삭제
    df = df.drop('색상_추출', axis=1)
    
    extracted_count = (df['색상'].str.strip() != '').sum()
    print(f"✅ 색상 추출 완료: {extracted_count}개 상품에 색상 정보")
    
    # 3단계 결과 저장
    df.to_csv(TEMP_FILES['step3'], index=False, encoding='utf-8-sig')
    print(f"💾 3단계 결과 저장: {TEMP_FILES['step3']}")
    
    return f"색상 추출 완료 - {extracted_count}개 상품 색상 정보 추가"

def filter_missing_data_task(**context):
    """4단계: 필수 데이터 필터링 (성별, 원가 없으면 삭제)"""
    print("🔍 4단계: 필수 데이터 필터링 중...")
    
    # 이전 단계 결과 로드
    df = pd.read_csv(TEMP_FILES['step3'], encoding='utf-8-sig')
    initial_count = len(df)
    print(f"📂 이전 단계 데이터 로드: {initial_count}행")
    
    # 성별이 없는 행 제거
    df = df.dropna(subset=['성별'])
    df = df[df['성별'].str.strip() != '']
    
    # 원가가 없는 행 제거
    df = df.dropna(subset=['원가'])
    
    filtered_count = len(df)
    removed_count = initial_count - filtered_count
    print(f"✅ 필수 데이터 필터링 완료: {initial_count} → {filtered_count}행 (삭제: {removed_count}행)")
    
    # 4단계 결과 저장
    df.to_csv(TEMP_FILES['step4'], index=False, encoding='utf-8-sig')
    print(f"💾 4단계 결과 저장: {TEMP_FILES['step4']}")
    
    return f"필수 데이터 필터링 완료 - {removed_count}행 삭제, {filtered_count}행 유지"



def map_brands_task(**context):
    """5단계: 브랜드명 한글 매핑"""
    print("🏷️ 5단계: 브랜드명 매핑 중...")
    
    # 이전 단계 결과 로드
    df = pd.read_csv(TEMP_FILES['step4'], encoding='utf-8-sig')
    print(f"📂 이전 단계 데이터 로드: {len(df)}행")
    
    # 브랜드 매핑 로드
    brands_df = pd.read_csv(BRANDS_FILE, encoding='utf-8-sig')
    brands_mapping = dict(zip(brands_df['영어브랜드명'], brands_df['한글브랜드명']))
    
    # 브랜드 매핑 함수
    def map_brand(brand_name, brands_mapping):
        if pd.isna(brand_name):
            return None
        brand_name = str(brand_name).strip()
        if brand_name == "":
            return None
        if brand_name in brands_mapping:
            return brands_mapping[brand_name]
        brand_lower = brand_name.lower()
        for eng, kor in brands_mapping.items():
            if str(eng).lower() == brand_lower:
                return kor
        return None
    
    # apply로 매핑 적용
    df['브랜드명_한글'] = df['브랜드명'].apply(lambda x: map_brand(x, brands_mapping))
    
    # 매핑 성공률 확인
    mapped_count = df['브랜드명_한글'].notna().sum()
    total_count = len(df)
    print(f"✅ 브랜드 매핑 완료: {mapped_count}/{total_count} ({mapped_count/total_count*100:.1f}%)")
    
    # 다음 단계용 임시 파일 저장
    df.to_csv(TEMP_FILES['step5'], index=False, encoding='utf-8-sig')
    
    return "브랜드명 매핑 완료"


def remove_unmapped_brands_task(**context):
    """6단계: 매핑 불가능한 브랜드 제거"""
    print("❌ 6단계: 매핑 불가능한 브랜드 제거 중...")
    
    # 이전 단계 결과 로드
    df = pd.read_csv(TEMP_FILES['step5'], encoding='utf-8-sig')
    initial_count = len(df)
    print(f"📂 이전 단계 데이터 로드: {initial_count}행")
    
    # 매핑되지 않은 브랜드 제거
    df = df.dropna(subset=['브랜드명_한글'])
    final_count = len(df)
    removed_count = initial_count - final_count
    
    print(f"✅ 매핑 불가능한 브랜드 제거 완료: {initial_count} → {final_count}행 (삭제: {removed_count}행)")
    
    # 6단계 결과 저장
    df.to_csv(TEMP_FILES['step6'], index=False, encoding='utf-8-sig')
    print(f"💾 6단계 결과 저장: {TEMP_FILES['step6']}")
    
    return f"브랜드 제거 완료 - {removed_count}행 삭제, {final_count}행 유지"

def process_categories_task(**context):
    """7단계: 카테고리 전처리 (소분류 → 대분류 매핑)"""
    print("📂 7단계: 카테고리 전처리 중...")
    
    # 이전 단계 결과 로드
    df = pd.read_csv(TEMP_FILES['step6'], encoding='utf-8-sig')
    print(f"📂 이전 단계 데이터 로드: {len(df)}행")
    
    # 카테고리 매핑 정의
    category_mapping = {
        '상의': ['후드티', '셔츠/블라우스', '긴소매', '반소매', '피케/카라', '니트/스웨터', '슬리브리스'],
        '바지': ['데님팬츠', '트레이닝/조거팬츠', '코튼팬츠', '슈트팬츠/슬랙스', '숏팬츠', '카고팬츠'],
        '원피스': ['미니원피스', '미디원피스', '맥시원피스'],
        '스커트': ['미니스커트', '미디스커트', '롱스커트']
    }
    
    def standardize_subcategory(subcategory, main_category=None):
        """소분류 표준화 (대분류에 따라 정확한 매핑)"""
        if pd.isna(subcategory):
            return None
        
        subcategory = str(subcategory).strip()
        
        # 기본 매핑 규칙
        basic_mappings = {
            '트레이닝/조거': '트레이닝/조거팬츠',
            '카고': '카고팬츠',
            '조거': '트레이닝/조거팬츠',
            '슬랙스': '슈트팬츠/슬랙스',
            '쇼츠': '숏팬츠',
            '긴팔': '긴소매',
            '반팔': '반소매',
            '스웻': '니트/스웨터',
            '터틀넥': '니트/스웨터',
            '치노': '코튼팬츠',
            '후드': '후드티',
            '셔츠': '셔츠/블라우스',
            '블라우스': '셔츠/블라우스',
            '데님': '데님팬츠',
            '피케': '피케/카라',
            '카라': '피케/카라',
            '슬리브리스': '슬리브리스'
        }
        
        # 기본 매핑 적용
        for old_term, new_term in basic_mappings.items():
            if old_term in subcategory:
                return new_term
        
        # 대분류에 따른 길이별 매핑
        if main_category == '원피스':
            if '미니' in subcategory:
                return '미니원피스'
            elif '미디' in subcategory:
                return '미디원피스'
            elif '롱' in subcategory or '맥시' in subcategory:
                return '맥시원피스'
            else:
                return '미디원피스'  # 기본값
        elif main_category == '스커트':
            if '미니' in subcategory:
                return '미니스커트'
            elif '미디' in subcategory:
                return '미디스커트'
            elif '롱' in subcategory:
                return '롱스커트'
            else:
                return '미디스커트'  # 기본값
        
        # 매핑되지 않은 경우 None 반환 (삭제 대상)
        return None
    
    def map_subcategory_to_main(subcategory):
        if pd.isna(subcategory):
            return None
        
        subcategory = str(subcategory).strip()
        
        # 각 대분류별로 소분류 매핑
        for main_cat, sub_cats in category_mapping.items():
            for sub_cat in sub_cats:
                if sub_cat in subcategory:
                    return main_cat
        
        # 특별한 경우 처리
        if '티셔츠' in subcategory:
            return '상의'
        elif '팬츠' in subcategory or '바지' in subcategory:
            return '바지'
        elif '원피스' in subcategory:
            return '원피스'
        elif '스커트' in subcategory:
            return '스커트'
        
        return None
    
    # 대분류가 상의/바지/원피스/스커트가 아닌 데이터 모두 제거
    valid_categories = ['상의', '바지', '원피스', '스커트']
    before_filter = len(df)
    
    df = df[df['대분류'].isin(valid_categories)]
    after_filter = len(df)
    removed_count = before_filter - after_filter
    
    print(f"🗑️ 유효하지 않은 대분류 제거: {removed_count}행 삭제")
    print(f"📊 필터링 후 데이터: {after_filter}행")
    
    # 소분류만 표준화 (기존 대분류 정보 사용)
    df['소분류_정리'] = df.apply(
        lambda row: standardize_subcategory(row['소분류'], row['대분류']), 
        axis=1
    )
    
    # 매핑되지 않은 소분류 확인 및 제거
    unmapped = df[df['소분류_정리'].isna()]
    if len(unmapped) > 0:
        unique_unmapped = unmapped['소분류'].unique()
        print(f"⚠️ 매핑되지 않은 소분류 ({len(unique_unmapped)}개): {list(unique_unmapped)[:10]}...")
        
        # 매핑되지 않은 행들 제거
        before_removal = len(df)
        df = df.dropna(subset=['소분류_정리'])
        after_removal = len(df)
        removed_count = before_removal - after_removal
        
        print(f"🗑️ 매핑되지 않은 소분류 제거: {removed_count}행 삭제")
        print(f"📊 제거 후 데이터: {after_removal}행")
    
    print(f"✅ 카테고리 필터링 완료")
    
    # 7단계 결과 저장
    df.to_csv(TEMP_FILES['step7'], index=False, encoding='utf-8-sig')
    print(f"💾 7단계 결과 저장: {TEMP_FILES['step7']}")
    
    return "카테고리 전처리 완료"

def save_processed_data_task(**context):
    """8단계: 최종 데이터 저장"""
    print("💾 8단계: 최종 데이터 저장 중...")
    
    # 이전 단계 결과 로드
    df = pd.read_csv(TEMP_FILES['step7'], encoding='utf-8-sig')
    print(f"📂 이전 단계 데이터 로드: {len(df)}행")
    
    # 컬럼명 변경 및 재구성
    final_df = df.copy()
    
    # 브랜드명 컬럼 변경
    final_df['한글브랜드명'] = final_df['브랜드명_한글']
    final_df['영어브랜드명'] = final_df['브랜드명']
    
    # 소분류 컬럼만 변경 (대분류는 디렉토리에서 이미 설정됨)
    final_df['소분류'] = final_df['소분류_정리']
    
    # 사이트명 컬럼 추가
    final_df['사이트명'] = 'wconcept'
    
    # 필요한 컬럼만 선택 (순서 조정)
    columns_to_save = [
        '상품코드', '상품명', '한글브랜드명', '영어브랜드명', 
        '대분류', '소분류', '원가', '할인가', 
        '성별', '이미지URL', '소재', '색상', '좋아요수', '상품링크', '사이트명'
    ]
    
    # 존재하는 컬럼만 선택
    existing_columns = [col for col in columns_to_save if col in final_df.columns]
    final_df = final_df[existing_columns]
    
    # 최종 결과 저장
    final_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    
    # 임시 파일 정리
    cleanup_temp_files()
    
    # 최종 통계 출력
    print("=" * 50)
    print("✅ 전처리 파이프라인 완료!")
    print(f"💾 최종 파일 저장: {OUTPUT_FILE}")
    print(f"\n📈 최종 통계:")
    print(f"- 총 상품 수: {len(final_df):,}개")
    print(f"- 총 컬럼 수: {len(final_df.columns)}개")
    print(f"- 브랜드 수: {final_df['한글브랜드명'].nunique():,}개")
    print(f"- 대분류별 분포:")
    if '대분류' in final_df.columns:
        category_counts = final_df['대분류'].value_counts()
        for category, count in category_counts.items():
            print(f"  • {category}: {count:,}개")
    
    return f"최종 데이터 저장 완료 - {len(final_df):,}행, {len(existing_columns)}컬럼"

def cleanup_temp_files():
    """임시 파일 정리"""
    print("🗑️ 임시 파일 정리 중...")
    cleaned_count = 0
    
    for step_name, file_path in TEMP_FILES.items():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                cleaned_count += 1
                print(f"  ✅ 삭제: {file_path}")
        except Exception as e:
            print(f"  ⚠️ 삭제 실패 {file_path}: {e}")
    
    print(f"🗑️ 임시 파일 정리 완료: {cleaned_count}개 파일 삭제")

# DAG 태스크 정의
start = DummyOperator(
    task_id='start', 
    dag=dag,
    doc_md="전처리 파이프라인 시작"
)

load_data = PythonOperator(
    task_id='load_data',
    python_callable=load_data_task,
    dag=dag,
    doc_md="1단계: 원본 데이터 로드 및 브랜드 매핑 준비"
)

clean_product_names = PythonOperator(
    task_id='clean_product_names',
    python_callable=clean_product_names_task,
    dag=dag,
    doc_md="2단계: 상품명 정리 (괄호, 특수문자 제거)"
)

extract_colors = PythonOperator(
    task_id='extract_colors',
    python_callable=extract_colors_task,
    dag=dag,
    doc_md="3단계: 상품명에서 색상 정보 추출 및 보완"
)

filter_missing_data = PythonOperator(
    task_id='filter_missing_data',
    python_callable=filter_missing_data_task,
    dag=dag,
    doc_md="4단계: 필수 데이터 필터링 (성별, 원가 없는 상품 제거)"
)

map_brands = PythonOperator(
    task_id='map_brands',
    python_callable=map_brands_task,
    dag=dag,
    doc_md="5단계: 영어 브랜드명을 한글 브랜드명으로 매핑"
)

remove_unmapped_brands = PythonOperator(
    task_id='remove_unmapped_brands',
    python_callable=remove_unmapped_brands_task,
    dag=dag,
    doc_md="6단계: 매핑되지 않은 브랜드 데이터 제거"
)

process_categories = PythonOperator(
    task_id='process_categories',
    python_callable=process_categories_task,
    dag=dag,
    doc_md="7단계: 카테고리 정리 (소분류 표준화 및 대분류 매핑)"
)

save_processed_data = PythonOperator(
    task_id='save_processed_data',
    python_callable=save_processed_data_task,
    dag=dag,
    doc_md="8단계: 최종 전처리 데이터 저장 및 임시파일 정리"
)

# 컴바인 프로세싱 DAG 트리거
trigger_combined_preprocessor = TriggerDagRunOperator(
    task_id='trigger_combined_preprocessor',
    trigger_dag_id='combined_preprocessor',
    wait_for_completion=False,
    poke_interval=10,
    allowed_states=['success'],
    failed_states=['failed'],
    dag=dag,
    doc_md="""
    ## 컴바인 프로세싱 DAG 자동 실행
    
    ### 기능
    - wconcept 전처리 완료 후 자동으로 컴바인 프로세싱 DAG 실행
    - 모든 사이트 데이터 결합 및 S3 업로드
    
    ### 실행 흐름
    1. wconcept 전처리 완료
    2. 컴바인 프로세싱 DAG 자동 실행  
    3. 최종 통합 CSV 파일 생성 및 S3 업로드
    """
)

end = DummyOperator(
    task_id='end', 
    dag=dag,
    doc_md="전처리 파이프라인 완료"
)

# DAG 의존성 설정
start >> load_data >> clean_product_names >> extract_colors >> filter_missing_data >> map_brands >> remove_unmapped_brands >> process_categories >> save_processed_data >> trigger_combined_preprocessor >> end