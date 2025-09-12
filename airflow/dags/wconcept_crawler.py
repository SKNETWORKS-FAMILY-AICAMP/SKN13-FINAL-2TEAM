from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
import os
import time
import re
import csv
import boto3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium_stealth import stealth

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
    'wconcept_product_crawling',
    default_args=default_args,
    description='W컨셉 상품 링크 크롤링 DAG',
    schedule_interval=None,  # 수동 실행
    max_active_runs=1,
    tags=['crawling', 'wconcept', 'ecommerce']
)

class S3Uploader:
    """S3 업로드 유틸리티 (링크 CSV 업로드용)"""
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
            print("❌ AWS 키가 없어 S3 업로드를 사용할 수 없습니다.")
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
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    # options.add_argument('--disable-images')  # 이미지 로딩 활성화 (상품 감지용)
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 타임아웃 설정
    options.add_argument('--page-load-strategy=eager')  # DOM 로딩 완료시 바로 다음 단계
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)  # 페이지 로딩 타임아웃 30초
    
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

def wait_for_products_to_load(driver, max_wait=20):
    """상품들이 완전히 로딩될 때까지 대기"""
    print("🔄 상품 로딩 대기 중...")
    
    # W컨셉 사이트에 특화된 선택자들
    selectors_to_try = [
        "div.product-item",
        ".product-card", 
        ".item",
        ".goods-item",
        ".product",
        "a[href*='/Product/']",
        "[data-product-id]",
        "[data-goods-id]",
        ".goods-list .item",  # W컨셉 특화
        ".product-list .item",  # W컨셉 특화
        ".goods-list li",  # W컨셉 특화
        ".product-list li",  # W컨셉 특화
        "[class*='product']",  # product가 포함된 클래스
        "[class*='goods']",  # goods가 포함된 클래스
        "[class*='item']"  # item이 포함된 클래스
    ]
    
    for selector in selectors_to_try:
        try:
            # 최소 5개 이상의 상품이 로딩될 때까지 대기 (기준 낮춤)
            WebDriverWait(driver, max_wait).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) >= 5
            )
            count = len(driver.find_elements(By.CSS_SELECTOR, selector))
            print(f"✅ '{selector}' 선택자로 상품 로딩 완료 ({count}개)")
            return selector
        except:
            continue
    
    # 마지막 시도: 단순히 상품 요소가 있는지만 확인
    for selector in selectors_to_try:
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            count = len(driver.find_elements(By.CSS_SELECTOR, selector))
            print(f"⚠️ '{selector}' 선택자로 기본 로딩 완료 ({count}개)")
            return selector
        except:
            continue
    
    print("❌ 상품을 찾을 수 없습니다")
    return None

def scroll_to_load_all_products(driver, expected_count=60):
    """모든 상품이 로딩될 때까지 스크롤"""
    print(f"🔄 모든 상품 로딩을 위한 스크롤 시작 (예상: {expected_count}개)")
    
    scroll_pause_time = 3  # 대기 시간 증가
    max_scrolls = 100  # 최대 스크롤 횟수 대폭 증가
    last_product_count = 0
    no_change_count = 0
    
    # W컨셉 특화 선택자들 (정확한 순서로)
    initial_selectors = [
        ".goods-list .item",  # W컨셉 특화 (가장 정확)
        ".product-list .item",  # W컨셉 특화
        ".goods-list li",  # W컨셉 특화
        ".product-list li",  # W컨셉 특화
        "a[href*='/Product/']",  # 상품 링크가 있는 요소
        "[data-product-id]",  # 상품 ID가 있는 요소
        "[data-goods-id]",  # 상품 ID가 있는 요소
        "div.product-item",
        ".product-card", 
        ".goods-item",
        ".product",
        "[class*='product']",  # product가 포함된 클래스
        "[class*='goods']",  # goods가 포함된 클래스
        "[class*='item']"  # item이 포함된 클래스
    ]
    
    # 초기 상품 개수 확인
    for selector in initial_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            last_product_count = len(elements)
            print(f"📍 초기 {selector}: {last_product_count}개")
            break
    
    # 1단계: 세밀한 스크롤 (6개씩 10줄 = 60개를 위해)
    print("🔄 1단계: 세밀한 스크롤 시작...")
    for i in range(max_scrolls):
        # 현재 페이지 높이 확인
        current_height = driver.execute_script("return document.body.scrollHeight;")
        viewport_height = driver.execute_script("return window.innerHeight;")
        
        # 더 세밀한 스크롤 (한 줄씩 로딩되도록)
        scroll_step = viewport_height * 0.3  # 스크롤 간격을 더 줄임
        target_scroll = scroll_step * (i + 1)
        
        # 스크롤 실행
        driver.execute_script(f"window.scrollTo(0, {target_scroll});")
        print(f"📜 스크롤 {i+1}/{max_scrolls}: {target_scroll}px")
        time.sleep(scroll_pause_time)
        
        # 새로운 상품 개수 확인
        current_count = 0
        for selector in initial_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                current_count = len(elements)
                break
        
        # 상품 개수 변화 확인
        if current_count == last_product_count:
            no_change_count += 1
            print(f"⚠️ 상품 개수 변화 없음 ({current_count}개) - {no_change_count}/10")
            if no_change_count >= 10:  # 10번 연속 변화 없으면 종료
                print(f"✅ 상품 개수 변화 없음 ({current_count}개), 스크롤 종료")
                break
        else:
            no_change_count = 0
            print(f"📈 상품 개수 증가: {last_product_count} → {current_count}")
        
        last_product_count = current_count
        
        # 예상 개수에 도달하면 종료
        if current_count >= expected_count:
            print(f"✅ 예상 개수({expected_count}개) 도달, 스크롤 종료")
            break
        
        # 페이지 끝에 도달했는지 확인
        new_height = driver.execute_script("return document.body.scrollHeight;")
        if new_height == current_height and target_scroll >= current_height:
            print(f"✅ 페이지 끝에 도달, 스크롤 종료")
            break
    
    # 2단계: 강화된 스크롤 (더 세밀하게)
    print("🔄 2단계: 강화된 스크롤 시작...")
    for i in range(20):  # 횟수 증가
        # 페이지 맨 아래까지 스크롤
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # 위로 조금 올라가서 다시 스크롤
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 500);")
        time.sleep(1)
        
        # 다시 맨 아래로
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # 상품 개수 재확인
        current_count = 0
        for selector in initial_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                current_count = len(elements)
                break
        
        print(f"🔄 강화 스크롤 {i+1}/20: {current_count}개")
        
        if current_count > last_product_count:
            last_product_count = current_count
            no_change_count = 0
        else:
            no_change_count += 1
            if no_change_count >= 5:  # 5번 연속 변화 없으면 종료
                break
    
    # 3단계: 무한 스크롤 시뮬레이션
    print("🔄 3단계: 무한 스크롤 시뮬레이션...")
    for i in range(10):  # 횟수 증가
        # 키보드 End 키 시뮬레이션
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(3)
        
        # 마우스 휠 스크롤 시뮬레이션
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(2)
        
        # 상품 개수 재확인
        current_count = 0
        for selector in initial_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                current_count = len(elements)
                break
        
        print(f"🔄 무한 스크롤 {i+1}/10: {current_count}개")
        
        if current_count > last_product_count:
            last_product_count = current_count
        else:
            no_change_count += 1
            if no_change_count >= 3:
                break
    
    # 4단계: 최종 강화 스크롤
    print("🔄 4단계: 최종 강화 스크롤...")
    for i in range(5):
        # 천천히 맨 아래까지 스크롤
        total_height = driver.execute_script("return document.body.scrollHeight;")
        for j in range(0, total_height, 200):
            driver.execute_script(f"window.scrollTo(0, {j});")
            time.sleep(0.5)
        
        # 맨 아래에서 잠시 대기
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        # 상품 개수 재확인
        current_count = 0
        for selector in initial_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                current_count = len(elements)
                break
        
        print(f"🔄 최종 강화 스크롤 {i+1}/5: {current_count}개")
        
        if current_count > last_product_count:
            last_product_count = current_count
        else:
            break
    
    # 최종 상품 개수 확인
    final_count = 0
    for selector in initial_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            final_count = len(elements)
            break
    
    print(f"🎯 최종 상품 개수: {final_count}개")
    return final_count

def extract_product_links(soup, category_name):
    """BeautifulSoup을 사용하여 상품 링크 추출"""
    all_links = []
    
    # W컨셉 상품 링크 검증 함수
    def is_valid_product_link(link):
        """유효한 상품 링크인지 검증"""
        if not link or not isinstance(link, str):
            return False
        
        # W컨셉 상품 링크 패턴 확인
        if not link.startswith('https://www.wconcept.co.kr/Product/'):
            return False
        
        # 상품 ID가 숫자인지 확인
        product_id = link.split('/Product/')[-1]
        if not product_id.isdigit():
            return False
        
        # 상품 ID 길이 확인 (보통 6-10자리)
        if len(product_id) < 6 or len(product_id) > 10:
            return False
        
        return True
    
    # 정확한 상품 링크 추출 방법들
    extraction_methods = [
        # 방법 1: 직접적인 상품 링크 추출 (가장 정확)
        lambda: [
            link['href'] if link['href'].startswith('http') else "https://www.wconcept.co.kr" + link['href']
            for link in soup.find_all('a', href=True)
            if '/Product/' in link['href'] and is_valid_product_link(
                link['href'] if link['href'].startswith('http') else "https://www.wconcept.co.kr" + link['href']
            )
        ],
        
        # 방법 2: W컨셉 특화 선택자로 추출
        lambda: [
            "https://www.wconcept.co.kr/Product/" + re.search(r'/(\d+)', link['href']).group(1)
            for link in soup.select(".goods-list a[href*='/Product/'], .product-list a[href*='/Product/']")
            if re.search(r'/(\d+)', link['href']) and is_valid_product_link(
                "https://www.wconcept.co.kr/Product/" + re.search(r'/(\d+)', link['href']).group(1)
            )
        ],
        
        # 방법 3: 상품 카드 내부 링크
        lambda: [
            "https://www.wconcept.co.kr/Product/" + re.search(r'/(\d+)', link['href']).group(1)
            for link in soup.select(".goods-card a[href*='/Product/'], .product-card a[href*='/Product/']")
            if re.search(r'/(\d+)', link['href']) and is_valid_product_link(
                "https://www.wconcept.co.kr/Product/" + re.search(r'/(\d+)', link['href']).group(1)
            )
        ],
        
        # 방법 4: data-product-id 속성에서 추출
        lambda: [
            "https://www.wconcept.co.kr/Product/" + item['data-product-id']
            for item in soup.find_all(attrs={'data-product-id': True})
            if item['data-product-id'].isdigit() and is_valid_product_link(
                "https://www.wconcept.co.kr/Product/" + item['data-product-id']
            )
        ],
        
        # 방법 5: 이미지 src에서 상품 ID 추출 (W컨셉 패턴)
        lambda: [
            "https://www.wconcept.co.kr/Product/" + re.search(r'/(\d+)_', img['src']).group(1)
            for img in soup.find_all('img', src=True)
            if re.search(r'/(\d+)_', img.get('src', '')) and is_valid_product_link(
                "https://www.wconcept.co.kr/Product/" + re.search(r'/(\d+)_', img['src']).group(1)
            )
        ]
    ]
    
    for i, method in enumerate(extraction_methods, 1):
        try:
            links = method()
            if links:
                # 중복 제거
                unique_method_links = list(set(links))
                print(f"✅ 방법 {i}로 {len(unique_method_links)}개 유효한 링크 추출")
                all_links.extend(unique_method_links)
        except Exception as e:
            print(f"⚠️ 방법 {i} 실패: {e}")
    
    # 최종 중복 제거 및 검증
    unique_links = []
    seen_ids = set()
    
    for link in all_links:
        if is_valid_product_link(link):
            product_id = link.split('/Product/')[-1]
            if product_id not in seen_ids:
                unique_links.append(link)
                seen_ids.add(product_id)
    
    # 정렬
    unique_links = sorted(unique_links, key=lambda x: int(x.split('/Product/')[-1]))
    
    print(f"🎯 '{category_name}'에서 총 {len(unique_links)}개의 유효한 상품 링크 추출")
    
    # 디버깅: 처음 5개 링크 출력
    if unique_links:
        print("📋 추출된 링크 샘플:")
        for i, link in enumerate(unique_links[:5], 1):
            print(f"   {i}. {link}")
    
    return unique_links

def crawl_category_links(category_name, base_url, total_pages, **context):
    """
    주어진 카테고리 정보를 바탕으로 W컨셉 상품 링크를 크롤링합니다.
    """
    print(f"\n{'='*30}")
    print(f"▶▶▶ '{category_name}' 카테고리 크롤링 시작 (총 {total_pages} 페이지)")
    print(f"{'='*30}")
    
    driver = setup_chrome_driver()
    all_product_links = []

    try:
        for page_num in range(1, total_pages + 1):
            url = f"{base_url}&page={page_num}" if '?' in base_url else f"{base_url}?page={page_num}"
            
            try:
                print(f"📍 페이지 로딩 중: {url}")
                driver.get(url)
                
                # 상품 로딩 대기
                active_selector = wait_for_products_to_load(driver)
                if not active_selector:
                    print(f"❌ {page_num}페이지에서 상품을 찾을 수 없습니다")
                    continue
                
                # 모든 상품이 로딩될 때까지 스크롤
                final_count = scroll_to_load_all_products(driver, expected_count=60)
                
                # 스크롤 후 추가 대기
                time.sleep(3)
                
                # 추가 로딩 대기 (동적 콘텐츠 완전 로딩)
                print("🔄 동적 콘텐츠 추가 로딩 대기...")
                for i in range(10):  # 횟수 증가
                    # 맨 아래로 스크롤
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # 맨 위로 스크롤
                    driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
                    
                    # 중간 지점으로 스크롤
                    total_height = driver.execute_script("return document.body.scrollHeight;")
                    driver.execute_script(f"window.scrollTo(0, {total_height // 2});")
                    time.sleep(1)
                
                # 페이지 소스 파싱
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # 상품 링크 추출
                page_links = extract_product_links(soup, category_name)
                all_product_links.extend(page_links)
                
                print(f"📊 스크롤 결과: {final_count}개 상품 감지, {len(page_links)}개 링크 추출")
                
                # 만약 60개 미만이면 추가 시도
                if len(page_links) < 60:
                    print(f"⚠️ {len(page_links)}개만 수집됨. 추가 시도 중...")
                    
                    # 강화된 추가 스크롤
                    for attempt in range(3):  # 3번 시도
                        print(f"🔄 추가 시도 {attempt + 1}/3...")
                        time.sleep(5)
                        
                        # 천천히 맨 아래까지 스크롤
                        total_height = driver.execute_script("return document.body.scrollHeight;")
                        for j in range(0, total_height, 100):
                            driver.execute_script(f"window.scrollTo(0, {j});")
                            time.sleep(0.3)
                        
                        # 맨 아래에서 잠시 대기
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(5)
                        
                        # 다시 파싱
                        soup = BeautifulSoup(driver.page_source, 'html.parser')
                        additional_links = extract_product_links(soup, category_name)
                        
                        if len(additional_links) > len(page_links):
                            page_links = additional_links
                            all_product_links = all_product_links[:-len(page_links)] + page_links
                            print(f"✅ 추가 시도 {attempt + 1} 성공: {len(page_links)}개 링크")
                            break
                        else:
                            print(f"⚠️ 추가 시도 {attempt + 1} 실패: 여전히 {len(page_links)}개")
                    
                    if len(page_links) < 60:
                        print(f"❌ 최종 실패: {len(page_links)}개만 수집됨")
                
                # 최종 검증: 실제 상품 링크만 필터링
                valid_links = []
                for link in page_links:
                    if (link.startswith('https://www.wconcept.co.kr/Product/') and 
                        link.split('/Product/')[-1].isdigit() and
                        len(link.split('/Product/')[-1]) >= 6):
                        valid_links.append(link)
                
                if len(valid_links) != len(page_links):
                    print(f"🔍 링크 검증: {len(page_links)}개 → {len(valid_links)}개 유효한 링크")
                    page_links = valid_links
                    all_product_links = all_product_links[:-len(page_links)] + page_links
                
                print(f"✅ '{category_name}' {page_num}/{total_pages} 페이지 크롤링 완료 (수집: {len(page_links)}개, 누적: {len(all_product_links)}개)")
                
                # 페이지 간 간격
                time.sleep(3)

            except Exception as e:
                print(f"❗️ '{category_name}' {page_num}페이지 처리 중 오류: {e}")
                continue

    except Exception as e:
        print(f"❌ '{category_name}' 크롤링 중 전체 오류: {e}")
        raise
    finally:
        driver.quit()

    # 중복 제거 및 정렬
    unique_links = sorted(list(set(all_product_links)))
    print(f"\n🚀 '{category_name}' 카테고리에서 총 {len(unique_links)}개의 고유 링크 수집 완료!")
    
    # XCom을 통해 결과 전달
    context['task_instance'].xcom_push(key=f'{category_name}_links', value=unique_links)
    context['task_instance'].xcom_push(key=f'{category_name}_count', value=len(unique_links))
    
    return unique_links

def save_to_csv_task(category_name, save_path='link', **context):
    """수집된 링크를 CSV 파일로 저장합니다."""
    # XCom에서 링크 데이터 가져오기
    links = context['task_instance'].xcom_pull(key=f'{category_name}_links')
    
    if not links:
        print(f"❌ '{category_name}' 링크 데이터가 없습니다.")
        return False
    
    # 저장 디렉토리 생성 (날짜별 폴더 구조)
    current_date = datetime.now().strftime('%Y%m%d')  # YYYYMMDD 형식
    full_save_path = os.path.join('/home/tjddml/w', save_path, current_date)  # link/날짜/ 형태
    os.makedirs(full_save_path, exist_ok=True)
    
    # 파일명 (카테고리명만)
    file_path = os.path.join(full_save_path, f"{category_name}.csv")
    
    try:
        with open(file_path, "w", newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['id', '링크'])
            for link in links:
                # URL에서 상품 ID 추출
                product_id = link.split('/Product/')[-1]
                writer.writerow([product_id, link])
        
        print(f"💾 [저장 성공] '{file_path}' 파일로 {len(links)}개 링크 저장 완료.")
        
        # 저장 결과를 XCom에 저장
        context['task_instance'].xcom_push(key=f'{category_name}_file_path', value=file_path)
        return True
        
    except IOError as e:
        print(f"❌ [저장 오류] '{file_path}' 저장 중 오류 발생: {e}")
        raise

def summary_task(**context):
    """전체 작업 결과 요약"""
    print("\n" + "="*50)
    print("📊 크롤링 작업 완료 요약")
    print("="*50)
    
    total_links = 0
    for task_config in CRAWLING_TASKS:
        category_name = task_config['name']
        count = context['task_instance'].xcom_pull(key=f'{category_name}_count')
        file_path = context['task_instance'].xcom_pull(key=f'{category_name}_file_path')
        
        if count:
            total_links += count
            print(f"✅ {category_name}: {count}개 링크 수집")
            print(f"   📁 파일: {file_path}")
        else:
            print(f"❌ {category_name}: 수집 실패")
    
    print(f"\n🎉 총 {total_links}개의 상품 링크가 수집되었습니다.")
    print("="*50)

# 크롤링 작업 설정
CRAWLING_TASKS = [
    {
        'name': '여자_티셔츠_신상품',
        'url': 'https://display.wconcept.co.kr/category/women/001003?sort=NEW',
        'pages': 1,
        'save_path': 'link'
    },
    {
        'name': '여자_스커트_신상품',
        'url': 'https://display.wconcept.co.kr/category/women/001007?sort=NEW',
        'pages': 1,
        'save_path': 'link'
    },
    {
        'name': '여자_바지_신상품',
        'url': 'https://display.wconcept.co.kr/category/women/001006?sort=NEW',
        'pages': 1,
        'save_path': 'link'
    },
    {
        'name': '남자_티셔츠_신상품',
        'url': 'https://display.wconcept.co.kr/category/men/001002?sort=NEW',
        'pages': 1,
        'save_path': 'link'
    },
    {
        'name': '남자_바지_신상품',
        'url': 'https://display.wconcept.co.kr/category/men/001005?sort=NEW',
        'pages': 1,
        'save_path': 'link'
    },
    {
        'name': '여자_원피스_신상품',
        'url': 'https://display.wconcept.co.kr/category/women/001005?sort=NEW',  
        'pages': 1,
        'save_path': 'link'
    },
]

# 시작 태스크
start_task = DummyOperator(
    task_id='start_crawling',
    dag=dag
)

# 동적으로 크롤링 및 저장 태스크 생성
crawling_tasks = []
saving_tasks = []

for task_config in CRAWLING_TASKS:
    category_name = task_config['name']
    
    # 크롤링 태스크
    crawl_task = PythonOperator(
        task_id=f'crawl_{category_name}',
        python_callable=crawl_category_links,
        op_kwargs={
            'category_name': category_name,
            'base_url': task_config['url'],
            'total_pages': task_config['pages']
        },
        dag=dag
    )
    
    # CSV 저장 태스크
    save_task = PythonOperator(
        task_id=f'save_{category_name}',
        python_callable=save_to_csv_task,
        op_kwargs={
            'category_name': category_name,
            'save_path': task_config['save_path']
        },
        dag=dag
    )
    
    # 태스크 의존성 설정
    start_task >> crawl_task >> save_task
    
    crawling_tasks.append(crawl_task)
    saving_tasks.append(save_task)

# 요약 태스크
summary = PythonOperator(
    task_id='crawling_summary',
    python_callable=summary_task,
    dag=dag
)

# 링크 CSV를 S3에 업로드 후 로컬에서 삭제
def upload_link_csvs_to_s3_and_cleanup(base_path='/home/tjddml/w/link', **context):
    try:
        if not os.path.exists(base_path):
            print(f"ℹ️ 링크 폴더 없음: {base_path}")
            return True

        # 최신 날짜(YYYYMMDD) 폴더 선택
        date_dirs = [d for d in os.listdir(base_path)
                     if os.path.isdir(os.path.join(base_path, d)) and len(d) == 8 and d.isdigit()]
        if not date_dirs:
            print("ℹ️ 날짜 폴더가 없어 업로드할 링크 CSV가 없습니다.")
            return True

        latest_date = max(date_dirs)
        latest_dir = os.path.join(base_path, latest_date)
        csv_files = [os.path.join(latest_dir, f) for f in os.listdir(latest_dir) if f.lower().endswith('.csv')]

        if not csv_files:
            print(f"ℹ️ 최근 폴더({latest_dir}) 내 CSV가 없습니다.")
            return True

        uploader = S3Uploader()
        if not uploader.s3_client:
            print("❌ S3 클라이언트 없음: 업로드/정리 생략")
            return True

        uploaded = 0
        for file_path in csv_files:
            try:
                filename = os.path.basename(file_path)
                s3_key = f"wconcept_link_csvs/{latest_date}/{filename}"
                print(f"🔄 업로드: {file_path} → s3://{uploader.bucket_name}/{s3_key}")
                uploader.s3_client.upload_file(file_path, uploader.bucket_name, s3_key, ExtraArgs={'ContentType': 'text/csv'})
                uploaded += 1
                # 업로드 성공 시 파일 삭제
                try:
                    os.remove(file_path)
                    print(f"🗑️ 로컬 삭제: {file_path}")
                except Exception as e:
                    print(f"⚠️ 로컬 삭제 실패: {file_path} - {e}")
            except Exception as e:
                print(f"❌ 업로드 실패: {file_path} - {e}")

        # 폴더가 비면 폴더 삭제
        try:
            if not os.listdir(latest_dir):
                os.rmdir(latest_dir)
                print(f"🗑️ 빈 날짜 폴더 삭제: {latest_dir}")
        except Exception as e:
            print(f"⚠️ 폴더 삭제 실패: {latest_dir} - {e}")

        print(f"📊 링크 CSV 업로드 완료: {uploaded}/{len(csv_files)} 성공")
        return True
    except Exception as e:
        print(f"❌ 링크 CSV 업로드/정리 중 오류: {e}")
        return True

upload_links_and_cleanup_task = PythonOperator(
    task_id='upload_link_csvs_to_s3_and_cleanup',
    python_callable=upload_link_csvs_to_s3_and_cleanup,
    dag=dag
)

# HTML 크롤링 DAG 트리거 태스크
trigger_html_crawler = TriggerDagRunOperator(
    task_id='trigger_html_crawler',
    trigger_dag_id='wconcept_html_crawler',
    dag=dag
)

# 모든 저장 태스크가 완료된 후 요약 실행 → 링크 CSV S3 업로드 및 로컬 정리 → HTML 크롤링 트리거
saving_tasks >> summary >> upload_links_and_cleanup_task >> trigger_html_crawler 