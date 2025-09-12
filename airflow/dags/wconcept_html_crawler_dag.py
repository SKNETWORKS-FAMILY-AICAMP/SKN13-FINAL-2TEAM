from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
import os
import csv
import time
import boto3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium_stealth import stealth

def convert_wsl_path(path):
    """경로 변환 함수 (WSL에서 실행 시 그대로 반환)"""
    return path

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

# DAG 정의 - DAG_ID가 유니크한지 확인
dag = DAG(
    'wconcept_html_crawler',  # 다른 DAG와 중복되지 않도록 변경
    default_args=default_args,
    description='W컨셉 CSV 파일들의 HTML 크롤링 DAG',
    schedule_interval=None,  # 수동 실행 또는 트리거로만 실행
    max_active_runs=1,
    tags=['crawling', 'wconcept', 'html', 'ecommerce']
)

class S3Uploader:
    """S3 업로드 유틸리티"""
    def __init__(self):
        try:
            self.aws_access_key_id = Variable.get("AWS_ACCESS_KEY_ID", default_var=None)
            self.aws_secret_access_key = Variable.get("AWS_SECRET_ACCESS_KEY", default_var=None)
            self.aws_region = Variable.get("AWS_REGION", default_var="ap-northeast-2")
            self.bucket_name = Variable.get("S3_BUCKET_NAME", default_var="ivle-malle")
        except Exception:
            self.aws_access_key_id = None
            self.aws_secret_access_key = None
            self.aws_region = "ap-northeast-2"
            self.bucket_name = "ivle-malle"

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

def setup_chrome_driver():
    """Chrome 드라이버 설정"""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 타임아웃 설정
        options.add_argument('--page-load-strategy=eager')
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        # 봇 감지 우회 설정
        stealth(driver,
                languages=["ko-KR", "ko"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                )
        
        return driver
    except Exception as e:
        print(f"❌ Chrome 드라이버 설정 실패: {e}")
        raise

def get_latest_csv_files(base_path='/home/tjddml/w/link', **context):
    """`link/최신날짜폴더(YYYYMMDD)/` 안의 CSV 파일들만 선택."""
    print(f"\n{'='*50}")
    print(f"🔍 최신 CSV 파일 검색 시작: {base_path}")
    print(f"{'='*50}")

    try:
        print(f"🔍 검색 경로: {base_path}")

        if not os.path.exists(base_path):
            print(f"❌ 경로가 존재하지 않습니다: {base_path}")
            context['task_instance'].xcom_push(key='csv_files', value=[])
            context['task_instance'].xcom_push(key='latest_date', value=None)
            return []

        # 1) 날짜 폴더(YYYYMMDD) 목록 수집
        date_dirs = []
        for name in os.listdir(base_path):
            dir_path = os.path.join(base_path, name)
            if os.path.isdir(dir_path) and len(name) == 8 and name.isdigit():
                date_dirs.append(name)

        csv_files = []
        latest_date = None

        if date_dirs:
            # 2) 가장 최신 날짜 폴더 선택
            latest_date = max(date_dirs)
            latest_dir_path = os.path.join(base_path, latest_date)
            print(f"📅 최신 날짜 폴더 선택: {latest_dir_path}")

            # 3) 해당 폴더의 CSV 파일만 수집
            for file in os.listdir(latest_dir_path):
                if file.lower().endswith('.csv'):
                    file_path = os.path.join(latest_dir_path, file)
                    csv_files.append(file_path)
                    print(f"✅ 발견: {file} (경로: {file_path})")

            print(f"\n📊 최신 날짜 {latest_date} 폴더의 CSV 파일 {len(csv_files)}개 발견")
        else:
            # 날짜 폴더가 없는 경우: 하위 호환 - base_path 바로 아래의 CSV 파일 사용
            print("⚠️ 날짜 폴더(YYYYMMDD)를 찾지 못해 기본 폴더 내 CSV를 검색합니다.")
            for file in os.listdir(base_path):
                if file.lower().endswith('.csv'):
                    file_path = os.path.join(base_path, file)
                    csv_files.append(file_path)
                    print(f"✅ 발견(폴백): {file} (경로: {file_path})")

            print(f"\n📊 폴백: 총 {len(csv_files)}개의 CSV 파일 발견")

        # XCom 저장
        context['task_instance'].xcom_push(key='csv_files', value=csv_files)
        context['task_instance'].xcom_push(key='latest_date', value=latest_date)

        return csv_files

    except Exception as e:
        print(f"❌ CSV 파일 검색 중 오류: {e}")
        context['task_instance'].xcom_push(key='csv_files', value=[])
        context['task_instance'].xcom_push(key='latest_date', value=None)
        return []

def scrape_and_save_html_from_csv(csv_filename, start_index=0, max_retries=3, restart_interval=50, max_links=None, **context):
    """
    하나의 CSV 파일을 읽어, 그 안의 모든 링크에 접속하여
    각각의 HTML 소스를 별도의 파일로 저장합니다.
    """
    driver = None
    
    try:
        # CSV 파일 존재 확인
        if not os.path.exists(csv_filename):
            print(f"❗️ [오류] '{csv_filename}' 파일을 찾을 수 없습니다.")
            return False
            
        # HTML 저장을 위한 기본 폴더 생성
        base_html_dir = '/home/tjddml/w/html'
        os.makedirs(base_html_dir, exist_ok=True)
        
        # CSV 파일 이름에 맞춰 결과를 저장할 폴더 생성
        output_dir = f"{os.path.splitext(os.path.basename(csv_filename))[0]}_html"
        full_output_dir = os.path.join(base_html_dir, output_dir)
        os.makedirs(full_output_dir, exist_ok=True)
        
        print(f"\n{'='*50}")
        print(f"▶ '{os.path.basename(csv_filename)}' 파일 처리를 시작합니다.")
        print(f"▶ HTML 파일은 '{full_output_dir}' 폴더에 저장됩니다.")
        print(f"{'='*50}")

        # Selenium WebDriver 설정
        driver = setup_chrome_driver()

        # CSV 파일 읽기
        all_links = []
        with open(csv_filename, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if '링크' in row and row['링크']:
                    all_links.append(row['링크'])

        total_links = len(all_links)
        if total_links == 0:
            print(f"🟡 '{csv_filename}' 파일에 처리할 링크가 없습니다.")
            return False
        
        # 테스트용으로 링크 수 제한 (선택사항)
        if max_links and max_links < total_links:
            all_links = all_links[:max_links]
            total_links = len(all_links)
            print(f"🧪 테스트 모드: {max_links}개 링크만 처리합니다.")
            
        links_to_scrape = all_links[start_index:]
        success_count = 0
        error_count = 0
        
        # 각 링크 순회 및 HTML 저장
        for i, url in enumerate(links_to_scrape, start=start_index + 1):
            # 메모리 최적화: 일정 간격으로 드라이버 재시작
            if i > 1 and (i - 1) % restart_interval == 0:
                print(f"🔄 메모리 최적화를 위해 드라이버 재시작 중... ({i-1}개 완료)")
                if driver:
                    driver.quit()
                driver = setup_chrome_driver()
                time.sleep(2)  # 재시작 후 잠시 대기
                
            # 진행률 표시 (10개마다)
            if i % 10 == 0 or i == len(links_to_scrape):
                progress = (i / len(links_to_scrape)) * 100
                print(f"📊 진행률: {progress:.1f}% ({i}/{len(links_to_scrape)})")
            
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    product_id = url.split('/')[-1].split('?')[0]
                    html_filepath = os.path.join(full_output_dir, f"{product_id}.html")
                    
                    if os.path.exists(html_filepath):
                        print(f"🟡 ({i}/{total_links}) [{product_id}.html] 이미 존재하므로 건너뜁니다.")
                        success_count += 1  # 이미 존재하는 것도 성공으로 카운트
                        break

                    driver.get(url)
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.pdt_info"))
                    )
                    time.sleep(1)

                    html_source = driver.page_source
                    with open(html_filepath, "w", encoding='utf-8') as file:
                        file.write(html_source)
                    
                    success_count += 1
                    print(f"✅ ({i}/{total_links}) [{product_id}.html] 저장 완료")
                    break  # 성공하면 루프 종료

                except TimeoutException:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"⚠️ ({i}/{total_links}) URL 로딩 시간 초과, 재시도 {retry_count}/{max_retries}: {url}")
                        time.sleep(2)  # 재시도 전 대기
                    else:
                        error_count += 1
                        print(f"❗️ ({i}/{total_links}) URL 로딩 시간 초과 (최종): {url}")
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"⚠️ ({i}/{total_links}) URL 처리 중 오류, 재시도 {retry_count}/{max_retries}: {url} | 오류: {e}")
                        time.sleep(2)  # 재시도 전 대기
                    else:
                        error_count += 1
                        print(f"❗️ ({i}/{total_links}) URL 처리 중 오류 발생 (최종): {url} | 오류: {e}")
        
        print(f"\n🎉 '{os.path.basename(csv_filename)}' 파일의 모든 링크 처리가 완료되었습니다.")
        print(f"📊 성공: {success_count}개, 실패: {error_count}개")
        
        # 성공률 계산
        print(f"✅ 크롤링 완료: {success_count}/{total_links} 링크")
        
        # 결과를 XCom에 저장
        result = {
            'csv_file': csv_filename,
            'total_links': total_links,
            'success_count': success_count,
            'error_count': error_count,
            'output_dir': full_output_dir
        }
        
        context['task_instance'].xcom_push(
            key=f'html_result_{os.path.basename(csv_filename)}', 
            value=result
        )
        
        return True
        
    except Exception as e:
        print(f"❌ CSV 파일 처리 중 예상치 못한 오류: {e}")
        return False
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def process_all_csv_files(max_retries=3, restart_interval=50, wait_time=1, timeout=20, max_links=None, **context):
    """발견된 모든 CSV 파일을 처리하는 통합 태스크"""
    try:
        csv_files = context['task_instance'].xcom_pull(task_ids='find_latest_csv_files', key='csv_files')
        
        if not csv_files:
            print("❌ 처리할 CSV 파일이 없습니다.")
            return True  # 실패로 처리하지 않고 정상 완료로 처리
        
        print(f"🔄 총 {len(csv_files)}개의 CSV 파일을 처리합니다.")
        
        results = []
        
        for csv_file in csv_files:
            try:
                print(f"\n처리 중: {csv_file}")
                result = scrape_and_save_html_from_csv(
                    csv_file, 
                    start_index=0, 
                    max_retries=max_retries, 
                    restart_interval=restart_interval,
                    max_links=max_links,
                    **context
                )
                results.append({
                    'file': csv_file,
                    'success': result
                })
            except Exception as e:
                print(f"❌ {csv_file} 처리 중 오류: {e}")
                results.append({
                    'file': csv_file,
                    'success': False,
                    'error': str(e)
                })
        
        # 결과 요약
        successful_files = [r for r in results if r['success']]
        failed_files = [r for r in results if not r['success']]
        
        print(f"\n🎉 모든 CSV 파일 처리 완료!")
        print(f"📊 성공: {len(successful_files)}개, 실패: {len(failed_files)}개")
        
        # XCom에 결과 저장
        context['task_instance'].xcom_push(key='processing_results', value=results)
        
        return True
        
    except Exception as e:
        print(f"❌ process_all_csv_files 실행 중 오류: {e}")
        raise

def html_crawling_summary(**context):
    """HTML 크롤링 작업 결과 요약"""
    try:
        print("\n" + "="*50)
        print("📊 HTML 크롤링 작업 완료 요약")
        print("="*50)
        
        csv_files = context['task_instance'].xcom_pull(task_ids='find_latest_csv_files', key='csv_files')
        latest_date = context['task_instance'].xcom_pull(task_ids='find_latest_csv_files', key='latest_date')
        
        if not csv_files:
            print("❌ 처리된 CSV 파일이 없습니다.")
            return True
        
        if latest_date:
            print(f"📅 처리된 날짜: {latest_date}")
        
        total_success = 0
        total_errors = 0
        processed_files = 0
        
        for csv_file in csv_files:
            csv_filename = os.path.basename(csv_file)
            result = context['task_instance'].xcom_pull(
                task_ids='process_all_csv_files',  # 태스크 ID 명시
                key=f'html_result_{csv_filename}'
            )
            
            if result:
                processed_files += 1
                print(f"✅ {csv_filename}:")
                print(f"   📊 총 링크: {result['total_links']}개")
                print(f"   ✅ 성공: {result['success_count']}개")
                print(f"   ❌ 실패: {result['error_count']}개")
                print(f"   📁 저장 경로: {result['output_dir']}")
                total_success += result['success_count']
                total_errors += result['error_count']
            else:
                print(f"❌ {csv_filename}: 처리 결과를 찾을 수 없습니다.")
        
        # 전체 성공률 계산
        total_links = total_success + total_errors
        print(f"\n🎉 전체 HTML 크롤링 완료!")
        print(f"📊 처리된 파일: {processed_files}개")
        print(f"📊 총 성공: {total_success}개, 총 실패: {total_errors}개")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"❌ 요약 생성 중 오류: {e}")
        return True  # 요약 실패해도 DAG 전체를 실패로 처리하지 않음

# 태스크 정의
start_task = DummyOperator(
    task_id='start_html_crawling',
    dag=dag
)

find_csv_task = PythonOperator(
    task_id='find_latest_csv_files',
    python_callable=get_latest_csv_files,
    dag=dag
)

# 운영용: 전체 링크 처리
html_crawling_task = PythonOperator(
    task_id='process_all_csv_files',
    python_callable=process_all_csv_files,
    op_kwargs={
        'max_retries': 3,        # 재시도 횟수
        'restart_interval': 50,  # 드라이버 재시작 간격
        'wait_time': 1,          # 페이지 로딩 후 대기 시간
        'timeout': 20,           # 페이지 로딩 타임아웃
        'max_links': None        # None이면 전체 링크 처리, 숫자면 해당 개수만 처리 (테스트: 5, 운영: None)
    },
    dag=dag
)

# 테스트용: 5개 링크만 처리
test_html_crawling_task = PythonOperator(
    task_id='test_process_all_csv_files',
    python_callable=process_all_csv_files,
    op_kwargs={
        'max_retries': 3,        # 재시도 횟수
        'restart_interval': 50,  # 드라이버 재시작 간격
        'wait_time': 1,          # 페이지 로딩 후 대기 시간
        'timeout': 20,           # 페이지 로딩 타임아웃
        'max_links': 5           # 테스트용으로 5개 링크만 처리
    },
    dag=dag
)

summary_task = PythonOperator(
    task_id='html_crawling_summary',
    python_callable=html_crawling_summary,
    dag=dag
)

# 태스크 의존성 설정
# 운영용: 전체 링크 처리
start_task >> find_csv_task >> html_crawling_task >> summary_task

# HTML to CSV 변환 DAG 자동 실행 태스크
trigger_html_to_csv_converter = TriggerDagRunOperator(
    task_id='trigger_html_to_csv_converter',
    trigger_dag_id='wconcept_html_to_csv_converter',
    wait_for_completion=False,  # 비동기 실행
    poke_interval=10,  # 10초마다 상태 확인
    allowed_states=['success'],  # 성공 상태에서만 트리거
    failed_states=['failed'],  # 실패 상태에서 트리거 안함
    dag=dag
)

# 테스트용을 사용하려면 아래 주석을 해제하고 위의 운영용을 주석 처리
# start_task >> find_csv_task >> test_html_crawling_task >> summary_task

# 태스크 의존성 설정 (HTML to CSV 변환 DAG 트리거 포함)
start_task >> find_csv_task >> html_crawling_task >> summary_task >> trigger_html_to_csv_converter