from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import os
import time
import requests
import json
import boto3
from botocore.exceptions import ClientError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from bs4 import BeautifulSoup


# WebDriver Manager 임포트
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pendulum

# 한국 시간대 설정
KST = pendulum.timezone('Asia/Seoul')



class S3Uploader:
    """S3에 데이터를 업로드하는 클래스"""
    
    def __init__(self):
        # Airflow 환경변수에서 AWS 키 가져오기
        self.aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.environ.get('AWS_REGION', 'ap-northeast-2')
        self.bucket_name = os.environ.get('S3_BUCKET_NAME', 'ivle-malle')
        
        # 환경변수 디버깅 (민감한 정보는 마스킹)
        print(f"🔍 환경변수 확인:")
        print(f"   AWS_ACCESS_KEY_ID: {'설정됨' if self.aws_access_key_id else '설정되지 않음'}")
        print(f"   AWS_SECRET_ACCESS_KEY: {'설정됨' if self.aws_secret_access_key else '설정되지 않음'}")
        print(f"   AWS_REGION: {self.aws_region}")
        print(f"   S3_BUCKET_NAME: {self.bucket_name}")
        
        # 환경변수가 없으면 에러 발생
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            print("❌ AWS 환경변수가 설정되지 않았습니다!")
            print("   Airflow UI → Admin → Variables에서 다음 변수들을 설정해주세요:")
            print("   - AWS_ACCESS_KEY_ID")
            print("   - AWS_SECRET_ACCESS_KEY")
            print("   - AWS_REGION (선택사항)")
            print("   - S3_BUCKET_NAME (선택사항)")
            self.s3_client = None
            return
        
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
    
    def upload_single_html(self, html_file, date_str, category):
        """단일 HTML 파일을 S3에 업로드"""
        try:
            # 파일 경로 확인
            if not os.path.exists(html_file):
                return f"❌ 파일이 존재하지 않음: {html_file}"
            
            # S3 키 생성: musinsa_htmls/{date}/{category}/{filename}
            filename = os.path.basename(html_file)
            s3_key = f"musinsa_htmls/{date_str}/{category}/{filename}"
            
            print(f"🔄 업로드 중: {html_file} → s3://{self.bucket_name}/{s3_key}")
            
            self.s3_client.upload_file(
                html_file,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'text/html'}
            )
            return f"✅ {filename} 업로드 완료"
        except Exception as e:
            return f"❌ {filename} 업로드 실패: {e}"
    
    def upload_html_files_parallel(self, html_files, category, date_str):
        """HTML 파일들을 병렬로 S3에 업로드합니다."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if not self.s3_client:
            print("❌ S3 클라이언트가 초기화되지 않았습니다.")
            return False
        
        print(f"🔄 {category} HTML 파일 {len(html_files)}개 S3 업로드 시작...")
        print(f"📁 파일 목록: {html_files}")
        
        # 병렬 업로드 (10개씩 동시 처리)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for html_file in html_files:
                future = executor.submit(self.upload_single_html, html_file, date_str, category)
                futures.append(future)
            
            # 모든 업로드 완료 대기
            success_count = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    print(result)
                    if "✅" in result:
                        success_count += 1
                except Exception as e:
                    print(f"❌ 업로드 처리 오류: {e}")
        
        print(f"📊 S3 업로드 완료: {success_count}/{len(html_files)} 성공")
        return success_count == len(html_files)

# Airflow Variables를 환경변수로 변환
from airflow.models import Variable

try:
    # Airflow Variables에서 값 가져오기
    aws_access_key = Variable.get("AWS_ACCESS_KEY_ID", default_var=None)
    aws_secret_key = Variable.get("AWS_SECRET_ACCESS_KEY", default_var=None)
    aws_region = Variable.get("AWS_REGION", default_var="ap-northeast-2")
    s3_bucket = Variable.get("S3_BUCKET_NAME", default_var="ivle-malle")
    
    if aws_access_key and aws_secret_key:
        # Variables를 환경변수로 설정
        os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_key
        os.environ['AWS_REGION'] = aws_region
        os.environ['S3_BUCKET_NAME'] = s3_bucket
        print("🔧 Airflow Variables를 환경변수로 변환 완료")
    else:
        print("❌ Airflow Variables가 설정되지 않았습니다!")
        print("   Airflow UI → Admin → Variables에서 다음 변수들을 설정해주세요:")
        print("   - AWS_ACCESS_KEY_ID")
        print("   - AWS_SECRET_ACCESS_KEY")
        print("   - AWS_REGION (선택사항)")
        print("   - S3_BUCKET_NAME (선택사항)")
        
except Exception as e:
    print(f"❌ Airflow Variables 로드 실패: {e}")
    print("   Airflow UI → Admin → Variables에서 다음 변수들을 설정해주세요:")
    print("   - AWS_ACCESS_KEY_ID")
    print("   - AWS_SECRET_ACCESS_KEY")
    print("   - AWS_REGION (선택사항)")
    print("   - S3_BUCKET_NAME (선택사항)")

# S3 업로더 인스턴스 생성
s3_uploader = S3Uploader()

def get_driver():
    """
    Selenium WebDriver를 초기화하고 반환합니다.
    WebDriver Manager를 사용하여 ChromeDriver 경로를 자동으로 관리합니다.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # 새로운 헤드리스 모드 사용
    chrome_options.add_argument("--no-sandbox")  # 샌드박스 비활성화 (Docker/CI 환경에서 필요)
    chrome_options.add_argument("--disable-dev-shm-usage") # /dev/shm 사용 비활성화 (Docker/CI 환경에서 필요)
    chrome_options.add_argument("user-agent=Mozilla/5.0") # User-Agent 설정

    # WebDriver Manager를 사용하여 ChromeDriver 경로를 자동으로 가져옵니다.
    service = Service(ChromeDriverManager().install())
    
    return webdriver.Chrome(service=service, options=chrome_options)

def is_valid_product(product_id):
    """
    주어진 product_id가 유효한 무신사 상품 페이지인지 확인합니다.
    HTTP 요청을 사용하여 404 응답이 아닌지 확인합니다.
    """
    url = f"https://www.musinsa.com/products/{product_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=3)
        return response.status_code != 404
    except requests.exceptions.RequestException as e:
        print(f"🚨 is_valid_product 요청 오류 ({product_id}): {e}")
        return False
    except Exception as e:
        print(f"🚨 is_valid_product 알 수 없는 오류 ({product_id}): {e}")
        return False

def get_product_category_fast(product_id):
    """
    HTTP 요청으로 빠르게 상품 카테고리를 확인합니다.
    Selenium보다 훨씬 빠르게 카테고리만 추출합니다.
    """
    url = f"https://www.musinsa.com/products/{product_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. breadcrumb 스타일 카테고리 탐색 (업데이트된 선택자)
        breadcrumb = soup.select("div.sc-1prswe3-1.sFSiu a")
        if breadcrumb:
            categories = [a.get_text(strip=True) for a in breadcrumb]
            for cat in categories:
                if cat in ["상의", "바지", "아우터", "신발", "가방", "액세서리"]:
                    return cat

        # 2. fallback: 전체 텍스트에서 키워드 검색
        html_text = response.text
        category_keywords = ["상의", "바지", "아우터", "신발", "가방", "액세서리"]
        for keyword in category_keywords:
            if keyword in html_text:
                return keyword

        return None

    except Exception as e:
        return None

    except requests.exceptions.RequestException as e:
        print(f"🚨 get_product_category_fast 요청 오류 ({product_id}): {e}")
        return None
    except Exception as e:
        print(f"🚨 get_product_category_fast 알 수 없는 오류 ({product_id}): {e}")
        return None

def load_last_product_ids():
    """마지막으로 크롤링한 상품 ID를 로드합니다."""
    config_file = "/home/tjddml/musinsa_htmls/last_product_id.json"
    default_id = 5253942
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 딕셔너리인 경우 가장 최근 날짜의 값 반환
            if isinstance(data, dict) and data:
                latest_date = max(data.keys())
                return data[latest_date]
            
            # 기존 형태(숫자)인 경우
            elif isinstance(data, (int, float)):
                return int(data)
            
        return default_id
        
    except Exception as e:
        print(f"⚠️ 설정 파일 로드 오류: {e}, 기본값 사용")
        return default_id

def save_last_product_id(last_id):
    """마지막으로 크롤링한 상품 ID를 날짜별로 저장합니다."""
    config_file = "/home/tjddml/musinsa_htmls/last_product_id.json"
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # 기존 데이터 로드
        existing_data = {}
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                existing_data = data
        
        # 오늘 날짜로 저장
        existing_data[today] = last_id
        
        # 디렉토리 생성
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        # 파일 저장
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
    except Exception as e:
        print(f"❌ 설정 파일 저장 오류: {e}")

def save_html_by_date(category, product_id, html_content):
    """상품 HTML을 날짜별 디렉토리에 저장합니다."""
    today = datetime.now().strftime('%Y-%m-%d')
    date_dir = f"/home/tjddml/musinsa_htmls/{today}/{category}"
    
    # 날짜별 디렉토리 생성
    os.makedirs(date_dir, exist_ok=True)
    
    html_file = f"{date_dir}/{product_id}.html"
    
    try:
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"💾 HTML 저장 완료: {html_file}")
        return html_file
    except Exception as e:
        print(f"❌ HTML 저장 오류 ({product_id}): {e}")
        return None

def click_all_tabs(driver):
    """
    모든 탭을 클릭하여 동적 콘텐츠를 로딩합니다.
    기존 코드의 탭 클릭 로직을 그대로 사용합니다.
    """
    try:
        # 탭 버튼들 찾기
        tab_buttons = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-mds='AccordionTrigger'] button"))
        )
        
        # 각 탭 클릭
        for tab in tab_buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", tab)
                driver.execute_script("arguments[0].click();", tab)
                time.sleep(1.2)
            except Exception as e:
                print(f"  ⚠️ 탭 클릭 실패(무시): {e}")
                continue
                
    except Exception as e:
        print(f"❗ 탭 버튼 탐색 실패: {e}")

def crawl_products():
    """
    무신사 웹사이트에서 상품 HTML을 크롤링합니다.
    하나의 스레드에서 카테고리를 확인하여 상의/하의 중 하나만 1개 수집하면 종료합니다.
    HTML은 날짜별 디렉토리에 저장되고 S3에도 업로드됩니다.
    """
    # 마지막 상품 ID 로드
    last_id = load_last_product_ids()
    print(f"📋 시작 상품 ID: {last_id}")
    print(f"📊 저장 모드: 날짜별 HTML 저장 + S3 업로드")
    print(f"🎯 테스트 모드: 상의 또는 하의 1개만 수집 후 종료")
    
    # 크롤링 결과 저장
    crawl_results = {
        'top': {'count': 0, 'last_id': last_id, 'files': []},
        'bottom': {'count': 0, 'last_id': last_id, 'files': []}
    }
    
    target_count = 1  # 테스트용: 1개만 수집
    
    # 시작 ID 설정
    product_id = last_id
    
    driver = None
    try:
        driver = get_driver()
        print(f"🚀 테스트용 단일 스레드 크롤링 시작... (시작 ID: {product_id})")
        
        # 상의나 하의 중 하나라도 수집되면 종료
        while crawl_results['top']['count'] < target_count and crawl_results['bottom']['count'] < target_count:
            # 유효한 상품 ID인지 확인
            if not is_valid_product(product_id):
                print(f"❌ {product_id} - 유효하지 않은 상품 (404)")
                product_id += 1
                continue
            
            # Selenium으로 카테고리 확인
            try:
                url = f"https://www.musinsa.com/products/{product_id}"
                driver.get(url)
                time.sleep(1.5)
                
                # 업데이트된 CSS 선택자 사용
                category_elem = driver.find_element(
                    By.CSS_SELECTOR,
                    "#root > div.sc-3weaze-0.kfGyOQ > div.sc-1puoja0-0.dSJyEH > div > div.sc-1prswe3-1.sFSiu.text-body_13px_reg.text-gray-600.font-pretendard > span:nth-child(1) > a"
                )
                category = category_elem.text.strip()
                
            except Exception as e:
                print(f"🚨 Selenium 카테고리 확인 오류 ({product_id}): {e}")
                product_id += 1
                continue
            
            # 카테고리별 처리
            if category == "상의":
                try:
                    print(f"🔍 {product_id} - {category} 상품 감지")
                    
                    # ✅ 탭 클릭 (모든 정보 로딩)
                    click_all_tabs(driver)
                    
                    # HTML 저장 (날짜별 디렉토리)
                    html_file = save_html_by_date('top', product_id, driver.page_source)
                    if html_file:
                        crawl_results['top']['files'].append(html_file)
                    
                    crawl_results['top']['count'] += 1
                    crawl_results['top']['last_id'] = product_id
                    
                    print(f"✅ top 저장 완료 ({crawl_results['top']['count']}/{target_count}): {product_id}")
                    
                    # 목표 달성 시 알림
                    if crawl_results['top']['count'] >= target_count:
                        print(f"🎯 top 목표 달성! ({target_count}개)")
                        print(f"🚀 테스트 완료! 상의 1개 수집됨 - 크롤링 종료")
                        break
                    else:
                        print(f"📈 top 추가 수집 중... ({crawl_results['top']['count']}/{target_count})")
                        
                except Exception as e:
                    print(f"🚨 Selenium 크롤링 오류 ({product_id}): {e}")
                    
            elif category == "바지":
                try:
                    print(f"🔍 {product_id} - {category} 상품 감지")
                    
                    # ✅ 탭 클릭 (모든 정보 로딩)
                    click_all_tabs(driver)
                    
                    # HTML 저장 (날짜별 디렉토리)
                    html_file = save_html_by_date('bottom', product_id, driver.page_source)
                    if html_file:
                        crawl_results['bottom']['files'].append(html_file)
                    
                    crawl_results['bottom']['count'] += 1
                    crawl_results['bottom']['last_id'] = product_id
                    
                    print(f"✅ bottom 저장 완료 ({crawl_results['bottom']['count']}/{target_count}): {product_id}")
                    
                    # 목표 달성 시 알림
                    if crawl_results['bottom']['count'] >= target_count:
                        print(f"🎯 bottom 목표 달성! ({target_count}개)")
                        print(f"🚀 테스트 완료! 하의 1개 수집됨 - 크롤링 종료")
                        break
                    else:
                        print(f"📈 bottom 추가 수집 중... ({crawl_results['bottom']['count']}/{target_count})")
                        
                except Exception as e:
                    print(f"🚨 Selenium 크롤링 오류 ({product_id}): {e}")
                    
            else:
                # 카테고리가 다른 경우
                print(f"ℹ️ 카테고리 불일치 ({product_id}): {category}")
            
            product_id += 1
            
            # 무한 루프 방지 (최대 1000개 시도)
            if product_id > last_id + 1000:
                print(f"⚠️ 최대 시도 횟수 초과")
                break
            
            # 테스트 모드에서는 하나라도 수집되면 종료되므로 이 조건은 제거
            # (위에서 각각 break로 처리됨)
    
    finally:
        if driver:
            driver.quit()
    
    # S3 업로드
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n🔄 S3 업로드 시작...")
    
    # 상의 HTML S3 업로드
    if crawl_results['top']['files']:
        upload_success = s3_uploader.upload_html_files_parallel(crawl_results['top']['files'], 'top', today)
        if upload_success:
            print(f"✅ 상의 HTML S3 업로드 완료: {len(crawl_results['top']['files'])}개")
        else:
            print(f"❌ 상의 HTML S3 업로드 실패")
    
    # 하의 HTML S3 업로드
    if crawl_results['bottom']['files']:
        upload_success = s3_uploader.upload_html_files_parallel(crawl_results['bottom']['files'], 'bottom', today)
        if upload_success:
            print(f"✅ 하의 HTML S3 업로드 완료: {len(crawl_results['bottom']['files'])}개")
        else:
            print(f"❌ 하의 HTML S3 업로드 실패")
    
    # 마지막 상품 ID 저장 (가장 큰 ID + 1로 저장하여 중복 방지)
    final_last_id = max(crawl_results['top']['last_id'], crawl_results['bottom']['last_id']) + 1
    save_last_product_id(final_last_id)
    
    # 결과 출력
    print(f"\n📊 테스트 크롤링 완료 결과:")
    print(f"   상의: {crawl_results['top']['count']}개 (마지막 ID: {crawl_results['top']['last_id']})")
    print(f"   하의: {crawl_results['bottom']['count']}개 (마지막 ID: {crawl_results['bottom']['last_id']})")
    print(f"   다음 시작 ID: {final_last_id}")
    
    # 테스트 결과 요약
    total_collected = crawl_results['top']['count'] + crawl_results['bottom']['count']
    if total_collected > 0:
        print(f"🎉 테스트 성공! 총 {total_collected}개 상품 수집 완료")
    else:
        print(f"⚠️ 테스트 실패: 수집된 상품이 없습니다")
    
    return crawl_results

# Airflow DAG의 기본 인자 설정
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 8, 5, 15, 30),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
}

# Airflow DAG 정의
with DAG(
    dag_id='musinsa_crawler_html_only',
    default_args=default_args,
    description='무신사 상품 HTML 크롤링 - 테스트용',
    schedule_interval='0 1 * * *', 
    catchup=False,
    is_paused_upon_creation=False,  # ← 추가 (생성 즉시 활성화)
    tags=['musinsa', 'crawler', 'html', 'test', 'kst'],
) as dag:
    
    # HTML 크롤링 태스크
    task_crawl_html = PythonOperator(
        task_id='crawl_html_only',
        python_callable=crawl_products,
        doc_md="""
        ## 무신사 상품 HTML 크롤링 (테스트용)
        
        ### 기능
        - 단일 스레드에서 카테고리를 확인하여 상의/하의 중 하나만 1개 수집 후 즉시 종료
        - 마지막 상품 ID 자동 저장 및 복원
        - 날짜별 디렉토리에 HTML 파일 저장
        - 모든 탭을 클릭하여 동적 콘텐츠 완전 로딩
        - S3에 HTML 파일 병렬 업로드
        
        ### 테스트 모드 특징
        - 상의 또는 하의 중 먼저 발견되는 카테고리 1개만 수집
        - 수집 완료 즉시 크롤링 종료
        - 빠른 테스트 및 검증 가능
        
        ### 저장 구조
        ```
        로컬:
        /home/tjddml/musinsa_htmls/
        ├── 2025-01-27/
        │   ├── top/ (상의 1개)
        │   └── bottom/ (하의 1개)
        └── last_product_id.json
        
        S3:
        s3://ivle-malle/musinsa_htmls/
        ├── 2025-01-27/
        │   ├── top/
        │   └── bottom/
        ```
        
        ### 특징
        - 빠른 테스트용 크롤링
        - HTML만 저장하여 별도 CSV 변환 도구와 연동 가능
        - 날짜별 디렉토리 구조로 데이터 관리 용이
        - 카테고리별 분리 저장
        - 단일 스레드로 효율적인 카테고리 분류
        - 모든 탭 클릭으로 완전한 HTML 수집
        - S3에 병렬 업로드로 빠른 저장
        """
    )

    # CSV 변환 DAG 자동 실행 태스크
    trigger_csv_converter = TriggerDagRunOperator(
        task_id='trigger_csv_converter',
        trigger_dag_id='musinsa_csv_converter_dag',
        wait_for_completion=False,  # 비동기 실행
        poke_interval=10,  # 10초마다 상태 확인
        allowed_states=['success'],  # 성공 상태에서만 트리거
        failed_states=['failed'],  # 실패 상태에서 트리거 안함
        doc_md="""
        ## CSV 변환 DAG 자동 실행
        
        ### 기능
        - HTML 크롤링 완료 후 자동으로 CSV 변환 DAG 실행
        - 로컬 HTML 파일 읽기 → CSV 변환 → S3 업로드
        
        ### 실행 흐름
        1. HTML 크롤링 완료
        2. CSV 변환 DAG 자동 실행
        3. 최종 CSV 파일 생성 및 S3 업로드
        """
    )

    # 태스크 의존성 설정
    task_crawl_html >> trigger_csv_converter
