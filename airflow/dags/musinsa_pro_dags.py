from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import pandas as pd
import os
import ast
import boto3
from botocore.exceptions import ClientError
import logging
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# DAG 기본 설정
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
}

# S3CSVLoader 클래스 (환경변수 사용)
class S3CSVLoader:
    """S3에서 CSV 파일을 로드하는 클래스 (환경변수 사용)"""
    
    def __init__(self):
        self.s3_client = None
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.aws_region = "ap-northeast-2"
        self.bucket_name = "ivle-malle"
        self.initialized = False
        
    def initialize(self):
        """S3 클라이언트 초기화 (환경변수 사용)"""
        if self.initialized:
            return True
            
        try:
            logger.info(f"🔍 환경변수에서 자격 증명 로드 중...")
            
            # .env 파일 로드 시도
            try:
                load_dotenv()
                logger.info(f"✅ .env 파일 로드 완료")
            except Exception as e:
                logger.warning(f"⚠️ .env 파일 로드 실패 (시스템 환경변수 사용): {e}")
            
            # 환경변수에서 자격 증명 로드
            self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            self.aws_region = os.getenv('AWS_REGION', 'ap-northeast-2')
            self.bucket_name = os.getenv('S3_BUCKET_NAME', 'ivle-malle')
            
            logger.info(f"✅ 환경변수 로드 완료")
        except Exception as e:
            logger.error(f"❌ 환경변수 로드 실패: {e}")
            logger.error(f"   .env 파일 또는 시스템 환경변수에서 다음 변수들을 설정해주세요:")
            logger.error(f"   - AWS_ACCESS_KEY_ID")
            logger.error(f"   - AWS_SECRET_ACCESS_KEY")
            logger.error(f"   - AWS_REGION (선택사항)")
            logger.error(f"   - S3_BUCKET_NAME (선택사항)")
            return False
        
        # 자격 증명 확인
        logger.info(f"🔍 AWS 설정 확인:")
        logger.info(f"   AWS_ACCESS_KEY_ID: {'설정됨' if self.aws_access_key_id else '설정되지 않음'}")
        logger.info(f"   AWS_SECRET_ACCESS_KEY: {'설정됨' if self.aws_secret_access_key else '설정되지 않음'}")
        logger.info(f"   AWS_REGION: {self.aws_region}")
        logger.info(f"   S3_BUCKET_NAME: {self.bucket_name}")
        
        # 자격 증명이 없으면 에러 발생
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            logger.error("❌ AWS 자격 증명이 설정되지 않았습니다!")
            logger.error("   .env 파일 또는 시스템 환경변수에서 다음 변수들을 설정해주세요:")
            logger.error("   - AWS_ACCESS_KEY_ID")
            logger.error("   - AWS_SECRET_ACCESS_KEY")
            logger.error("   - AWS_REGION (선택사항)")
            logger.error("   - S3_BUCKET_NAME (선택사항)")
            return False
        
        # 자격 증명 형식 검증
        if len(self.aws_access_key_id) != 20:
            logger.warning(f"⚠️ Access Key 길이가 올바르지 않습니다: {len(self.aws_access_key_id)} (예상: 20)")
            logger.warning(f"   Access Key: {self.aws_access_key_id[:5]}...{self.aws_access_key_id[-5:]}")
            return False
        if len(self.aws_secret_access_key) != 40:
            logger.warning(f"⚠️ Secret Key 길이가 올바르지 않습니다: {len(self.aws_secret_access_key)} (예상: 40)")
            logger.warning(f"   Secret Key: {self.aws_secret_access_key[:5]}...{self.aws_secret_access_key[-5:]}")
            return False
        
        # 자격 증명 디버깅 (처음/마지막 5자만 표시)
        logger.info(f"🔍 자격 증명 디버깅:")
        logger.info(f"   Access Key: {self.aws_access_key_id[:5]}...{self.aws_access_key_id[-5:]}")
        logger.info(f"   Secret Key: {self.aws_secret_access_key[:5]}...{self.aws_secret_access_key[-5:]}")
        logger.info(f"   Access Key 길이: {len(self.aws_access_key_id)}")
        logger.info(f"   Secret Key 길이: {len(self.aws_secret_access_key)}")
        
        # 자격 증명 정리 (공백 제거)
        self.aws_access_key_id = self.aws_access_key_id.strip()
        self.aws_secret_access_key = self.aws_secret_access_key.strip()
        logger.info(f"🔧 자격 증명 정리 후:")
        logger.info(f"   Access Key: {self.aws_access_key_id[:5]}...{self.aws_access_key_id[-5:]}")
        logger.info(f"   Secret Key: {self.aws_secret_access_key[:5]}...{self.aws_secret_access_key[-5:]}")
        
        try:
            # S3 클라이언트 초기화
            logger.info(f"🔧 S3 클라이언트 초기화 중...")
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
            logger.info(f"✅ S3 클라이언트 초기화 완료: {self.bucket_name}")
            
            # 연결 테스트 (권한 문제 시 건너뛰기)
            try:
                logger.info(f"🔍 S3 연결 테스트 중...")
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"✅ S3 연결 테스트 성공")
            except ClientError as e:
                if e.response['Error']['Code'] == '403':
                    logger.warning(f"⚠️ S3 연결 테스트 실패 (권한 부족), 계속 진행합니다: {e}")
                else:
                    raise e
            
            self.initialized = True
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"❌ S3 클라이언트 초기화 실패: {error_code} - {error_message}")
            
            if error_code == 'AccessDenied':
                logger.error(f"💡 해결 방법:")
                logger.error(f"   1. AWS IAM에서 해당 사용자에게 S3 권한을 부여하세요")
                logger.error(f"   2. 필요한 권한: s3:GetObject, s3:ListBucket, s3:HeadBucket")
                logger.error(f"   3. 버킷 이름이 올바른지 확인하세요: {self.bucket_name}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"💡 버킷이 존재하지 않습니다: {self.bucket_name}")
            elif error_code == 'SignatureDoesNotMatch':
                logger.error(f"💡 자격 증명이 올바르지 않습니다. .env 파일 또는 환경변수를 확인하세요")
            
            self.s3_client = None
            return False
            
        except Exception as e:
            logger.error(f"❌ S3 클라이언트 초기화 실패: {e}")
            self.s3_client = None
            return False
    
    def load_csv_from_s3(self, s3_key, encoding='utf-8'):
        """
        S3에서 CSV 파일을 로드하여 pandas DataFrame으로 반환
        
        Args:
            s3_key (str): S3 객체 키 (예: 'musinsa_csvs/2025-08-06/product_info_combined_1357.csv')
            encoding (str): 파일 인코딩 (기본값: 'utf-8')
        
        Returns:
            pandas.DataFrame: 로드된 CSV 데이터
        """
        if not self.s3_client:
            logger.error("❌ S3 클라이언트가 초기화되지 않았습니다.")
            return None
        
        try:
            logger.info(f"📥 S3에서 CSV 파일 로드 중: s3://{self.bucket_name}/{s3_key}")
            
            # S3에서 파일 다운로드
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            
            # CSV 데이터 읽기 (여러 인코딩 시도)
            try:
                df = pd.read_csv(response['Body'], encoding=encoding)
            except UnicodeDecodeError:
                logger.info(f"⚠️ {encoding} 인코딩 실패, cp949 시도...")
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                df = pd.read_csv(response['Body'], encoding='cp949')
            except Exception as e:
                logger.info(f"⚠️ cp949 인코딩 실패, euc-kr 시도...")
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                df = pd.read_csv(response['Body'], encoding='euc-kr')
            
            logger.info(f"✅ CSV 파일 로드 완료: {len(df)} 행, {len(df.columns)} 열")
            logger.info(f"📊 컬럼: {list(df.columns)}")
            
            return df
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"❌ 파일을 찾을 수 없습니다: s3://{self.bucket_name}/{s3_key}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"❌ 버킷을 찾을 수 없습니다: {self.bucket_name}")
            else:
                logger.error(f"❌ S3 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ CSV 파일 로드 실패: {e}")
            return None
    
    def get_latest_date_csv_files(self, base_prefix='musinsa_csvs/'):
        """
        가장 최근 날짜의 CSV 파일들을 찾아서 반환
        
        Args:
            base_prefix (str): 기본 접두사 (기본값: 'musinsa_csvs/')
        
        Returns:
            tuple: (최근 날짜, CSV 파일 키 리스트)
        """
        if not self.s3_client:
            logger.error("❌ S3 클라이언트가 초기화되지 않았습니다.")
            return None, []
        
        try:
            logger.info(f"🔍 가장 최근 날짜의 CSV 파일 검색 중: s3://{self.bucket_name}/{base_prefix}")
            
            # 모든 객체 조회
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=base_prefix
            )
            
            if 'Contents' not in response:
                logger.warning(f"⚠️ {base_prefix} 접두사로 시작하는 파일이 없습니다.")
                return None, []
            
            # 날짜별로 파일 그룹화
            date_files = {}
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('.csv') and 'product_info_' in key:
                    # 날짜 추출 (musinsa_csvs/YYYY-MM-DD/filename.csv)
                    parts = key.split('/')
                    if len(parts) >= 3:
                        date_str = parts[1]  # YYYY-MM-DD
                        if date_str not in date_files:
                            date_files[date_str] = []
                        date_files[date_str].append(key)
            
            if not date_files:
                logger.warning(f"⚠️ CSV 파일을 찾을 수 없습니다.")
                return None, []
            
            # 가장 최근 날짜 찾기
            latest_date = max(date_files.keys())
            latest_files = date_files[latest_date]
            
            logger.info(f"✅ 가장 최근 날짜: {latest_date}")
            logger.info(f"📄 해당 날짜의 CSV 파일 {len(latest_files)}개:")
            for file_key in latest_files:
                logger.info(f"   📄 {file_key}")
            
            return latest_date, latest_files
            
        except Exception as e:
            logger.error(f"❌ 최근 날짜 CSV 파일 검색 실패: {e}")
            return None, []
    
    def load_latest_csv_files(self, base_prefix='musinsa_csvs/', max_files=None):
        """
        가장 최근 날짜의 CSV 파일들을 로드
        
        Args:
            base_prefix (str): 기본 접두사 (기본값: 'musinsa_csvs/')
            max_files (int): 최대 로드할 파일 수 (None이면 모두 로드)
        
        Returns:
            tuple: (최근 날짜, pandas.DataFrame 리스트)
        """
        latest_date, csv_files = self.get_latest_date_csv_files(base_prefix)
        
        if not csv_files:
            logger.error("❌ 로드할 CSV 파일이 없습니다.")
            return None, []
        
        # 파일 수 제한
        if max_files and len(csv_files) > max_files:
            csv_files = csv_files[:max_files]
            logger.info(f"📝 최대 {max_files}개 파일만 로드합니다.")
        
        # CSV 파일들 로드
        dataframes = []
        for s3_key in csv_files:
            df = self.load_csv_from_s3(s3_key)
            if df is not None:
                dataframes.append(df)
                logger.info(f"✅ {s3_key} 로드 완료")
            else:
                logger.warning(f"⚠️ {s3_key} 로드 실패")
        
        return latest_date, dataframes

# 전역 S3CSVLoader 인스턴스
s3_loader = S3CSVLoader()

def load_brand_mapping():
    """브랜드 매핑 데이터 로드"""
    try:
        # DAG 파일이 있는 디렉토리에서 brands.csv 찾기
        dag_dir = os.path.dirname(os.path.abspath(__file__))
        brands_file = os.path.join(dag_dir, 'brands.csv')
        
        if not os.path.exists(brands_file):
            print(f"⚠️ brands.csv 파일을 찾을 수 없습니다: {brands_file}")
            return {}
            
        brand_df = pd.read_csv(brands_file, encoding='utf-8-sig')
        
        # 필수 컬럼 확인
        required_columns = ['한글브랜드명', '영어브랜드명']
        missing_columns = [col for col in required_columns if col not in brand_df.columns]
        if missing_columns:
            print(f"⚠️ brands.csv에 필수 컬럼이 없습니다: {missing_columns}")
            return {}
            
        brand_mapping = dict(zip(brand_df['한글브랜드명'], brand_df['영어브랜드명']))
        print(f"✅ 브랜드 매핑 로드 완료: {len(brand_mapping)}개 브랜드")
        return brand_mapping
    except Exception as e:
        print(f"❌ 브랜드 매핑 로드 실패: {e}")
        return {}

def normalize_columns(df):
    """컬럼명 정규화"""
    column_mapping = {
        '제품번호': '상품코드',
        '제품이름': '상품명',
        '브랜드명': '한글브랜드명',
        '제품대분류': '대분류',
        '제품소분류': '소분류',
        '사진': '이미지URL',
        '이미지 url': '이미지URL',
        '제품소재': '소재',
        '좋아요': '좋아요수',
        '좋아요 수': '좋아요수',
        '상품링크': '상품링크'
    }
    
    df = df.rename(columns=column_mapping)
    
    if '브랜드' in df.columns and '한글브랜드명' not in df.columns:
        df['한글브랜드명'] = df['브랜드']
    
    return df

def clean_product_name(name: str) -> str:
    """상품명 전처리"""
    if pd.isna(name):
        return ""
    
    import re
    
    name = str(name)  # 타입 안전성 보장
    name = re.sub(r"\[.*?\]|\(.*?\)|<.*?>", "", name)
    name = re.sub(r"[^가-힣a-zA-Z0-9\s]", "", name)
    
    remove_keywords = ["무료배송", "세일", "이벤트", "신상", "인기", "베스트", "핫딜", "남성", "여성"]
    for kw in remove_keywords:
        name = name.replace(kw, "")
    
    return name.strip()

def clean_data_quality(df):
    """데이터 품질 정리"""
    original_count = len(df)
    print(f"📊 원본 데이터 행 수: {original_count}")
    
    # 색상 필터링
    if '색상' in df.columns:
        before_count = len(df)
        df = df[~df['색상'].str.contains('상세', na=False)]
        df = df.dropna(subset=['색상'])
        df = df[df['색상'].str.strip() != '']
        print(f"📊 색상 필터링 후: {len(df)} (제거: {before_count - len(df)})")
    
    # 상품명 정리
    if '상품명' in df.columns:
        df['상품명'] = df['상품명'].apply(clean_product_name)
        before_count = len(df)
        df = df.dropna(subset=['상품명'])
        df = df[df['상품명'].str.strip() != '']
        print(f"📊 상품명 정리 후: {len(df)} (제거: {before_count - len(df)})")
    
    # 중복 제거 (상품명 8글자 기준)
    if '상품명' in df.columns:
        before_count = len(df)
        df['상품명_8글자'] = df['상품명'].str[:8]
        df = df.drop_duplicates(subset=['상품명_8글자'], keep='first')
        df = df.drop('상품명_8글자', axis=1)
        print(f"📊 중복 제거 후: {len(df)} (제거: {before_count - len(df)})")
    
    print(f"📊 최종 데이터 행 수: {len(df)} (전체 제거: {original_count - len(df)})")
    return df

def update_major_categories(df):
    """대분류 업데이트"""
    category_mapping = {
        '긴소매': '상의', '반소매': '상의', '후드티': '상의',
        '니트/스웨터': '상의', '셔츠/블라우스': '상의', '피케/카라': '상의', '슬리브리스': '상의',
        '숏팬츠': '바지', '데님팬츠': '바지', '코튼팬츠': '바지',
        '슈트팬츠/슬랙스': '바지', '카고팬츠': '바지', '트레이닝/조거팬츠': '바지',
        '롱스커트': '스커트', '미니스커트': '스커트', '미디스커트': '스커트',
        '맥시원피스': '원피스', '미니원피스': '원피스', '미디원피스': '원피스',
    }
    
    if '소분류' in df.columns:
        updated_count = 0
        for idx, row in df.iterrows():
            if row['소분류'] in category_mapping:
                df.at[idx, '대분류'] = category_mapping[row['소분류']]
                updated_count += 1
        print(f"📊 대분류 업데이트: {updated_count}개 행")
    
    return df

def map_subcategories(df):
    """소분류 매핑"""
    subcategory_mapping = {
        '긴소매티셔츠': '긴소매', '반소매티셔츠': '반소매', '니트스웨터': '니트/스웨터',
        '셔츠블라우스': '셔츠/블라우스', '피케카라': '피케/카라', '데님펜츠': '데님팬츠',
        '슈트팬츠슬랙스': '슈트팬츠/슬랙스', '트레이닝조거팬츠': '트레이닝/조거팬츠',
    }
    
    if '소분류' in df.columns:
        updated_count = 0
        for subcategory in subcategory_mapping:
            mask = df['소분류'] == subcategory
            df.loc[mask, '소분류'] = subcategory_mapping[subcategory]
            updated_count += mask.sum()
        print(f"📊 소분류 매핑: {updated_count}개 행")
    
    return df

def clean_gender_data(df):
    """성별 데이터 정리"""
    def map_gender_simple(gender_str):
        try:
            if pd.isna(gender_str):
                return '공용'
                
            if isinstance(gender_str, str):
                if gender_str.startswith('[') and gender_str.endswith(']'):
                    gender_list = ast.literal_eval(gender_str)
                else:
                    return gender_str
            else:
                gender_list = gender_str
                
            if gender_list == ['남성']:
                return '남성'
            elif gender_list == ['여성']:
                return '여성'
            elif gender_list == ['남성', '여성'] or gender_list == ['여성', '남성']:
                return '공용'
            elif gender_list == ['라이프']:
                return '공용'
            else:
                return '공용'  # 기본값
        except Exception as e:
            print(f"⚠️ 성별 데이터 파싱 오류: {gender_str} -> {e}")
            return '공용'
    
    if '성별' in df.columns:
        df['성별'] = df['성별'].apply(map_gender_simple)
        print(f"📊 성별 데이터 정리 완료")
    
    return df

def map_english_brand_names(df, brand_mapping):
    """한글브랜드명을 영어브랜드명으로 매핑"""
    if '한글브랜드명' in df.columns and brand_mapping:
        before_count = len(df)
        df['영어브랜드명'] = df['한글브랜드명'].map(brand_mapping)
        df = df.dropna(subset=['영어브랜드명'])
        print(f"📊 영어브랜드명 매핑 후: {len(df)} (제거: {before_count - len(df)})")
    elif not brand_mapping:
        print("⚠️ 브랜드 매핑 데이터가 없어 영어브랜드명 매핑을 건너뜁니다.")
    
    return df

def process_musinsa_csv_files(**context):
    """S3의 musinsa_csvs 디렉토리에서 최신 CSV 파일들을 다운로드하고 전처리하는 함수"""
    
    logger.info("🚀 무신사 CSV 처리 시작")
    
    # 브랜드 매핑 로드
    brand_mapping = load_brand_mapping()
    
    # S3CSVLoader 초기화
    if not s3_loader.initialize():
        raise Exception("S3CSVLoader 초기화 실패")
    
    logger.info(f"✅ S3CSVLoader 사용: {s3_loader.bucket_name}")
    
    try:
        # 가장 최근 날짜의 CSV 파일들 로드
        logger.info("🔍 가장 최근 날짜의 CSV 파일들을 로드합니다...")
        latest_date, dataframes = s3_loader.load_latest_csv_files(max_files=10)  # 최대 10개 파일
        
        if not latest_date or not dataframes:
            logger.error("❌ 로드할 CSV 파일이 없습니다.")
            raise Exception("로드할 CSV 파일이 없습니다.")
        
        logger.info(f"✅ {latest_date} 날짜의 CSV 파일 {len(dataframes)}개 로드 완료")
        
    except Exception as e:
        logger.error(f"❌ S3에서 파일 로드 실패: {e}")
        raise
    
    all_data = []
    successful_files = []
    failed_files = []
    
    # 각 DataFrame 처리
    for i, df in enumerate(dataframes):
        try:
            logger.info(f"📊 DataFrame {i+1} 처리 중: {len(df)}행, {len(df.columns)}열")
            
            # 데이터 전처리
            df = normalize_columns(df)
            df = clean_data_quality(df)
            df = update_major_categories(df)
            df = map_subcategories(df)
            df = clean_gender_data(df)
            df = map_english_brand_names(df, brand_mapping)
            df['사이트명'] = 'musinsa'
            
            logger.info(f"📊 처리된 데이터: {len(df)}행")
            
            if len(df) > 0:  # 데이터가 있을 때만 추가
                all_data.append(df)
                successful_files.append(f"DataFrame_{i+1}")
            else:
                logger.warning(f"⚠️ 처리 후 데이터가 없습니다: DataFrame_{i+1}")
                failed_files.append(f"DataFrame_{i+1}")
            
        except Exception as e:
            logger.error(f"❌ DataFrame 처리 실패 (DataFrame_{i+1}): {e}")
            failed_files.append(f"DataFrame_{i+1}")
            continue
    
    logger.info(f"📊 처리 결과:")
    logger.info(f"   성공: {len(successful_files)}개 파일")
    logger.info(f"   실패: {len(failed_files)}개 파일")
    
    if not all_data:
        logger.error("❌ 처리할 수 있는 데이터가 없습니다.")
        raise Exception("처리할 수 있는 데이터가 없습니다.")
    
    # 데이터 결합
    logger.info("🔄 데이터 결합 중...")
    combined_df = pd.concat(all_data, ignore_index=True)
    logger.info(f"📊 결합된 데이터: {len(combined_df)}행")
    
    # 최종 컬럼 선택
    final_columns = [
        '상품코드', '상품명', '대분류', '소분류', '원가', '할인가', 
        '이미지URL', '한글브랜드명', '성별', '좋아요수', '소재', 
        '색상', '상품링크', '영어브랜드명', '사이트명'
    ]
    
    available_columns = [col for col in final_columns if col in combined_df.columns]
    combined_df = combined_df[available_columns]
    
    logger.info(f"📊 최종 컬럼: {available_columns}")
    
    # 출력 파일 저장
    output_filename = f'/home/tjddml/airflow/musinsa/{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    combined_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    logger.info(f"💾 결과 저장: {output_filename}")
    
    # XCom에 결과 저장
    context['task_instance'].xcom_push(key='output_filename', value=output_filename)
    context['task_instance'].xcom_push(key='total_rows', value=len(combined_df))
    context['task_instance'].xcom_push(key='total_columns', value=len(combined_df.columns))
    context['task_instance'].xcom_push(key='successful_files', value=len(successful_files))
    context['task_instance'].xcom_push(key='failed_files', value=len(failed_files))
    context['task_instance'].xcom_push(key='latest_date', value=latest_date)
    
    logger.info("✅ 무신사 CSV 처리 완료")
    return output_filename

# DAG 정의
dag = DAG(
    'musinsa_data_processing',
    default_args=default_args,
    description='무신사 CSV 파일 전처리 DAG',
    schedule_interval=None,
    catchup=False,
    tags=['musinsa', 'data-processing']
)

# Task 정의
process_musinsa_task = PythonOperator(
    task_id='process_musinsa_csv_files',
    python_callable=process_musinsa_csv_files,
    dag=dag
)

# w컨셉 전처리 DAG 트리거
trigger_wconcept_preprocessor = TriggerDagRunOperator(
    task_id='trigger_wconcept_preprocessor_csv',
    trigger_dag_id='wconcept_preprocessor_csv',
    wait_for_completion=False,
    poke_interval=10,
    allowed_states=['success'],
    failed_states=['failed'],
    dag=dag,
    doc_md="""
    ## w컨셉 전처리 DAG 자동 실행
    
    ### 기능
    - 무신사 전처리 완료 후 자동으로 w컨셉 전처리 DAG 실행
    - w컨셉 데이터 전처리 및 정리
    
    ### 실행 흐름
    1. 무신사 전처리 완료
    2. w컨셉 전처리 DAG 자동 실행
    3. w컨셉 데이터 전처리 완료
    """
)

# Task 의존성 설정
process_musinsa_task >> trigger_wconcept_preprocessor