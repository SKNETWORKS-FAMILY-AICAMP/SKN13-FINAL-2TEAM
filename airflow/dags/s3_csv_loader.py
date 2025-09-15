import os
import pandas as pd
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class S3CSVLoader:
    """S3에서 CSV 파일을 로드하는 클래스"""
    
    def __init__(self):
        # .env 파일에서 환경변수 로드
        load_dotenv()
        
        # AWS 설정
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'ap-northeast-2')
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'ivle-malle')
        
        # AWS 키 존재 여부 확인
        logger.info(f"🔍 AWS 설정 확인:")
        logger.info(f"   AWS_ACCESS_KEY_ID: {'설정됨' if self.aws_access_key_id else '설정되지 않음'}")
        logger.info(f"   AWS_SECRET_ACCESS_KEY: {'설정됨' if self.aws_secret_access_key else '설정되지 않음'}")
        logger.info(f"   AWS_REGION: {self.aws_region}")
        logger.info(f"   S3_BUCKET_NAME: {self.bucket_name}")
        
        # AWS 키가 없으면 S3 클라이언트를 None으로 설정
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            logger.error("❌ AWS 환경변수가 설정되지 않았습니다!")
            logger.error("   .env 파일에서 다음 변수들을 설정해주세요:")
            logger.error("   - AWS_ACCESS_KEY_ID")
            logger.error("   - AWS_SECRET_ACCESS_KEY")
            logger.error("   - AWS_REGION (선택사항)")
            logger.error("   - S3_BUCKET_NAME (선택사항)")
            self.s3_client = None
            return
        
        # S3 클라이언트 초기화
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
            logger.info(f"✅ S3 클라이언트 초기화 완료: {self.bucket_name}")
        except Exception as e:
            logger.error(f"❌ S3 클라이언트 초기화 실패: {e}")
            self.s3_client = None
    
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
            
            # CSV 데이터 읽기
            df = pd.read_csv(response['Body'], encoding=encoding)
            
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
    
    def list_csv_files(self, prefix='musinsa_csvs/'):
        """
        S3 버킷에서 특정 접두사로 시작하는 CSV 파일 목록을 반환
        
        Args:
            prefix (str): 검색할 접두사 (기본값: 'musinsa_csvs/')
        
        Returns:
            list: CSV 파일 키 목록
        """
        if not self.s3_client:
            logger.error("❌ S3 클라이언트가 초기화되지 않았습니다.")
            return []
        
        try:
            logger.info(f"🔍 S3에서 CSV 파일 목록 조회 중: s3://{self.bucket_name}/{prefix}")
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            csv_files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.csv'):
                        csv_files.append(obj['Key'])
            
            logger.info(f"✅ CSV 파일 {len(csv_files)}개 발견")
            for file_key in csv_files:
                logger.info(f"   📄 {file_key}")
            
            return csv_files
            
        except Exception as e:
            logger.error(f"❌ CSV 파일 목록 조회 실패: {e}")
            return []
    
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
                if key.endswith('.csv'):
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
    
    def load_multiple_csvs(self, s3_keys, encoding='utf-8'):
        """
        여러 CSV 파일을 로드하여 리스트로 반환
        
        Args:
            s3_keys (list): S3 객체 키 리스트
            encoding (str): 파일 인코딩 (기본값: 'utf-8')
        
        Returns:
            list: pandas.DataFrame 리스트
        """
        dataframes = []
        
        for s3_key in s3_keys:
            df = self.load_csv_from_s3(s3_key, encoding)
            if df is not None:
                dataframes.append(df)
                logger.info(f"✅ {s3_key} 로드 완료")
            else:
                logger.warning(f"⚠️ {s3_key} 로드 실패")
        
        return dataframes

def main():
    """메인 함수 - 예제 사용법"""
    # S3CSVLoader 인스턴스 생성
    loader = S3CSVLoader()
    
    # 가장 최근 날짜의 CSV 파일들 로드
    print("🚀 가장 최근 날짜의 CSV 파일들을 로드합니다...")
    latest_date, dataframes = loader.load_latest_csv_files(max_files=5)  # 최대 5개 파일만 로드
    
    if latest_date and dataframes:
        print(f"\n✅ {latest_date} 날짜의 CSV 파일 {len(dataframes)}개 로드 완료!")
        
        # 각 DataFrame 정보 출력
        for i, df in enumerate(dataframes):
            print(f"\n📊 DataFrame {i+1}:")
            print(f"   📈 크기: {df.shape}")
            print(f"   📋 컬럼: {list(df.columns)}")
            print(f"   🔍 처음 3행:")
            print(df.head(3))
    else:
        print("❌ CSV 파일 로드 실패!")
    
    # 특정 CSV 파일 로드 예제 (기존 방식)
    print(f"\n🔍 특정 파일 로드 예제:")
    s3_key = "musinsa_csvs/2025-08-06/product_info_combined_1357.csv"
    df = loader.load_csv_from_s3(s3_key)
    
    if df is not None:
        print(f"✅ 특정 파일 로드 성공: {len(df)} 행")
    else:
        print("❌ 특정 파일 로드 실패!")

if __name__ == "__main__":
    main()
