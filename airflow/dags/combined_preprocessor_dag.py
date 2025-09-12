from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable
import pandas as pd
import os
import boto3
from botocore.exceptions import ClientError
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    'combined_preprocessor',
    default_args=default_args,
    description='각 사이트별 전처리된 CSV들을 합쳐서 S3에 업로드하는 DAG',
    schedule_interval=None,
    max_active_runs=1,
    tags=['preprocessing', 'data-combination', 's3-upload', 'ecommerce']
)

class S3Uploader:
    """S3 업로드 유틸리티"""
    def __init__(self):
        # Removed try-except for Airflow Variables, directly use os.getenv
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_REGION", "ap-northeast-2")
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "ivle-malle")

        if not self.aws_access_key_id or not self.aws_secret_access_key:
            print("❌ AWS 키 없음: S3 업로드 비활성화")
            self.s3_client = None
            return

        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
            print(f"✅ S3 클라이언트 초기화: {self.bucket_name}")
        except Exception as e:
            print(f"❌ S3 클라이언트 초기화 실패: {e}")
            self.s3_client = None

    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """파일을 S3에 업로드"""
        if not self.s3_client:
            print("❌ S3 클라이언트가 초기화되지 않았습니다")
            return False

        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            print(f"✅ S3 업로드 완료: {file_path} → s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            print(f"❌ S3 업로드 실패: {e}")
            return False
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
            return False

class DataCombiner:
    """데이터 결합 클래스"""
    def __init__(self):
        self.combined_df = None
        self.site_stats = {}
        
    def load_and_validate_csv(self, file_path: str, site_name: str) -> Optional[pd.DataFrame]:
        """CSV 파일 로드 및 검증"""
        try:
            if not os.path.exists(file_path):
                print(f"⚠️ 파일이 존재하지 않음: {file_path}")
                return None
                
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            print(f"✅ {site_name} 데이터 로드 완료: {len(df)}행, {len(df.columns)}컬럼")
            
            # 필수 컬럼 확인
            required_columns = ['상품코드', '상품명', '한글브랜드명', '영어브랜드명', 
                              '대분류', '소분류', '원가', '할인가', '성별', '사이트명']
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                print(f"⚠️ {site_name} 필수 컬럼 누락: {missing_columns}")
                return None
                
            return df
            
        except Exception as e:
            print(f"❌ {site_name} 데이터 로드 실패: {e}")
            return None
    
    def combine_data(self, csv_files: Dict[str, str]) -> pd.DataFrame:
        """여러 CSV 파일을 하나로 결합"""
        print("🔄 데이터 결합 시작...")
        
        dataframes = []
        
        for site_name, file_path in csv_files.items():
            df = self.load_and_validate_csv(file_path, site_name)
            if df is not None:
                # 사이트명 컬럼이 없으면 추가
                if '사이트명' not in df.columns:
                    df['사이트명'] = site_name
                
                dataframes.append(df)
                self.site_stats[site_name] = len(df)
                print(f"✅ {site_name}: {len(df)}행 추가")
            else:
                print(f"❌ {site_name}: 데이터 로드 실패로 제외")
        
        if not dataframes:
            raise ValueError("로드할 수 있는 데이터가 없습니다")
        
        # 데이터프레임 결합
        self.combined_df = pd.concat(dataframes, ignore_index=True)
        
        print(f"✅ 데이터 결합 완료: 총 {len(self.combined_df)}행")
        return self.combined_df
    
    def validate_combined_data(self) -> bool:
        """결합된 데이터 검증"""
        if self.combined_df is None:
            print("❌ 결합된 데이터가 없습니다")
            return False
        
        print("🔍 결합된 데이터 검증 중...")
        
        # 기본 검증
        total_rows = len(self.combined_df)
        total_columns = len(self.combined_df.columns)
        
        print(f"📊 데이터 크기: {total_rows}행 × {total_columns}컬럼")
        
        # 중복 상품코드 확인
        duplicate_codes = self.combined_df['상품코드'].duplicated().sum()
        if duplicate_codes > 0:
            print(f"⚠️ 중복 상품코드: {duplicate_codes}개")
        else:
            print("✅ 중복 상품코드 없음")
        
        # 사이트별 통계
        print("\n📈 사이트별 통계:")
        site_counts = self.combined_df['사이트명'].value_counts()
        for site, count in site_counts.items():
            print(f"  • {site}: {count}개")
        
        # 대분류별 통계
        print("\n📂 대분류별 통계:")
        category_counts = self.combined_df['대분류'].value_counts()
        for category, count in category_counts.items():
            print(f"  • {category}: {count}개")
        
        # 브랜드 통계
        unique_brands = self.combined_df['한글브랜드명'].nunique()
        print(f"\n🏷️ 고유 브랜드 수: {unique_brands}개")
        
        return True
    
    def save_combined_data(self, output_path: str) -> str:
        """결합된 데이터 저장"""
        if self.combined_df is None:
            raise ValueError("저장할 데이터가 없습니다")
        
        # 출력 디렉토리 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # CSV 저장
        self.combined_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        print(f"✅ 결합된 데이터 저장 완료: {output_path}")
        print(f"📁 파일 크기: {file_size:.2f} MB")
        
        return output_path

# DAG 태스크 함수들
def load_and_combine_data_task(**context):
    """데이터 로드 및 결합 태스크"""
    print("🚀 데이터 로드 및 결합 시작")

    # Dynamic path for 29cm data
    base_29cm_dir = r"/home/tjddml/airflow/Complete"
    latest_date_29cm_dir = None
    if os.path.exists(base_29cm_dir):
        for entry in os.listdir(base_29cm_dir):
            full_path = os.path.join(base_29cm_dir, entry)
            if os.path.isdir(full_path):
                try:
                    datetime.strptime(entry, '%Y_%m_%d')
                    if not latest_date_29cm_dir or entry > latest_date_29cm_dir:
                        latest_date_29cm_dir = entry
                except ValueError:
                    pass

    # Dynamic path for musinsa data
    base_musinsa_dir = r"/home/tjddml/airflow/musinsa"
    latest_musinsa_file = None
    if os.path.exists(base_musinsa_dir):
        musinsa_files = [f for f in os.listdir(base_musinsa_dir) if f.endswith('.csv')]
        if musinsa_files:
            # Sort files by name (which contains timestamp) to get the latest
            latest_musinsa_file = os.path.join(base_musinsa_dir, max(musinsa_files))

    # 전처리된 CSV 파일 경로들
    csv_files = {
        'wconcept': '/home/tjddml/airflow/dags/wconcept/processed_products.csv',
    }

    if latest_musinsa_file:
        csv_files['musinsa'] = latest_musinsa_file
    else:
        print(f"⚠️ Musinsa 파일이 존재하지 않음: {base_musinsa_dir}")

    if latest_date_29cm_dir:
        csv_files['29cm'] = os.path.join(base_29cm_dir, latest_date_29cm_dir, "29cm_preprocessing_product_info.csv")
    else:
        print(f"⚠️ 29cm 파일이 존재하지 않음: {base_29cm_dir}")

    # 실제 존재하는 파일만 필터링
    existing_files = {}
    for site, file_path in csv_files.items():
        if os.path.exists(file_path):
            existing_files[site] = file_path
        else:
            print(f"⚠️ {site} 파일이 존재하지 않음: {file_path}")
    
    if not existing_files:
        raise ValueError("로드할 수 있는 전처리된 CSV 파일이 없습니다")

    # 데이터 결합
    combiner = DataCombiner()
    combined_df = combiner.combine_data(existing_files)

    # 검증 (로그 출력용)
    combiner.validate_combined_data()

    # 결합된 데이터를 임시 CSV 파일로 저장하고 경로를 XCom으로 전달
    output_dir = "combined"
    os.makedirs(output_dir, exist_ok=True)
    combined_output_path = os.path.join(output_dir, "processed_products_combined.csv")
    combined_df.to_csv(combined_output_path, index=False, encoding="utf-8-sig")
    print(f"✅ 결합된 데이터 임시 저장 완료: {combined_output_path}")
    
    context['task_instance'].xcom_push(key='combined_csv_path', value=combined_output_path)

    return f"데이터 결합 완료: {len(combined_df)}행"

def save_combined_csv_task(**context):
    """결합된 CSV 저장 태스크"""
    print("💾 결합된 CSV 저장 시작")
    
    combiner = context['task_instance'].xcom_pull(key='combiner')
    output_path = "combined/processed_products_combined.csv"
    
    saved_path = combiner.save_combined_data(output_path)
    
    context['task_instance'].xcom_push(key='local_csv_path', value=saved_path)
    
    return f"로컬 CSV 저장 완료: {saved_path}"

def upload_to_s3_task(**context):
    """S3 업로드 태스크"""
    print("☁️ S3 업로드 시작")

    local_path = context['task_instance'].xcom_pull(key='combined_csv_path')

    if not local_path or not os.path.exists(local_path):
        raise ValueError(f"업로드할 파일이 존재하지 않음: {local_path}")

    # S3 업로더 초기화
    uploader = S3Uploader()

    # 현재 날짜를 포함한 S3 키 생성
    current_date = datetime.now().strftime("%Y%m%d")
    s3_key = f"processed_data/combined_products_{current_date}.csv"

    # S3 업로드
    success = uploader.upload_file(local_path, s3_key)

    if success:
        context['task_instance'].xcom_push(key='s3_key', value=s3_key)
        return f"S3 업로드 완료: s3://{uploader.bucket_name}/{s3_key}"
    else:
        raise Exception("S3 업로드 실패")

def generate_summary_report_task(**context):
    """요약 리포트 생성 태스크"""
    print("📋 요약 리포트 생성")

    combined_csv_path = context['task_instance'].xcom_pull(key='combined_csv_path')
    s3_key = context['task_instance'].xcom_pull(key='s3_key')

    if not combined_csv_path or not os.path.exists(combined_csv_path):
        print("⚠️ 결합된 CSV 파일 경로가 없거나 파일이 존재하지 않아 리포트를 생성할 수 없습니다")
        return "리포트 생성 실패"
    
    # CSV 파일에서 데이터 로드하여 combiner 객체 재생성
    combiner = DataCombiner()
    combiner.combined_df = pd.read_csv(combined_csv_path, encoding="utf-8-sig")
    combiner.site_stats = combiner.combined_df['사이트명'].value_counts().to_dict()

    # 요약 리포트 생성
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("📊 전처리된 데이터 결합 완료 리포트")
    report_lines.append("=" * 60)
    report_lines.append(f"📅 처리 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    # 전체 통계
    total_rows = len(combiner.combined_df)
    total_columns = len(combiner.combined_df.columns)
    report_lines.append(f"📈 전체 통계:")
    report_lines.append(f"  • 총 상품 수: {total_rows:,}개")
    report_lines.append(f"  • 총 컬럼 수: {total_columns}개")
    report_lines.append("")
    
    # 사이트별 통계
    report_lines.append("🏪 사이트별 통계:")
    site_counts = combiner.combined_df['사이트명'].value_counts()
    for site, count in site_counts.items():
        percentage = (count / total_rows) * 100
        report_lines.append(f"  • {site}: {count:,}개 ({percentage:.1f}%)")
    report_lines.append("")
    
    # 대분류별 통계
    report_lines.append("📂 대분류별 통계:")
    category_counts = combiner.combined_df['대분류'].value_counts()
    for category, count in category_counts.items():
        percentage = (count / total_rows) * 100
        report_lines.append(f"  • {category}: {count:,}개 ({percentage:.1f}%)")
    report_lines.append("")
    
    # 브랜드 통계
    unique_brands = combiner.combined_df['한글브랜드명'].nunique()
    report_lines.append(f"🏷️ 브랜드 통계:")
    report_lines.append(f"  • 고유 브랜드 수: {unique_brands:,}개")
    report_lines.append("")
    
    # S3 정보
    if s3_key:
        report_lines.append("☁️ S3 저장 정보:")
        report_lines.append(f"  • 저장 위치: s3://{S3Uploader().bucket_name}/{s3_key}")
        report_lines.append("")
    
    report_lines.append("✅ 모든 처리가 완료되었습니다!")
    report_lines.append("=" * 60)
    
    # 리포트 출력
    report = "\n".join(report_lines)
    print(report)
    
    # 리포트를 파일로 저장
    report_path = "combined/processing_report.txt"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"📄 리포트 저장 완료: {report_path}")
    
    return "요약 리포트 생성 완료"

# DAG 태스크 정의
start = DummyOperator(task_id='start', dag=dag)

load_and_combine_data = PythonOperator(
    task_id='load_and_combine_data',
    python_callable=load_and_combine_data_task,
    dag=dag
)

# save_combined_csv 태스크는 load_and_combine_data_task에 통합되므로 제거

upload_to_s3 = PythonOperator(
    task_id='upload_to_s3',
    python_callable=upload_to_s3_task,
    dag=dag
)

generate_summary_report = PythonOperator(
    task_id='generate_summary_report',
    python_callable=generate_summary_report_task,
    dag=dag
)

end = DummyOperator(task_id='end', dag=dag)

# DAG 의존성 설정
start >> load_and_combine_data >> upload_to_s3 >> generate_summary_report >> end
