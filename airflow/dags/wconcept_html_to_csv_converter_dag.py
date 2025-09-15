from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
import os
import pandas as pd
from bs4 import BeautifulSoup
import requests
import re
import boto3
from botocore.exceptions import ClientError

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

class S3Uploader:
    """S3에 CSV 파일을 업로드하는 클래스"""
    
    def __init__(self):
        # Airflow Variables에서 AWS 키 가져오기
        try:
            self.aws_access_key_id = Variable.get("AWS_ACCESS_KEY_ID", default_var=None)
            self.aws_secret_access_key = Variable.get("AWS_SECRET_ACCESS_KEY", default_var=None)
            self.aws_region = Variable.get("AWS_REGION", default_var="ap-northeast-2")
            self.bucket_name = Variable.get("S3_BUCKET_NAME", default_var="ivle-malle")
        except Exception as e:
            print(f"❌ Airflow Variables 로드 실패: {e}")
            self.aws_access_key_id = None
            self.aws_secret_access_key = None
            self.aws_region = "ap-northeast-2"
            self.bucket_name = "ivle-malle"
        
        # AWS 키 존재 여부 확인
        print(f"🔍 AWS 설정 확인:")
        print(f"   AWS_ACCESS_KEY_ID: {'설정됨' if self.aws_access_key_id else '설정되지 않음'}")
        print(f"   AWS_SECRET_ACCESS_KEY: {'설정됨' if self.aws_secret_access_key else '설정되지 않음'}")
        print(f"   AWS_REGION: {self.aws_region}")
        print(f"   S3_BUCKET_NAME: {self.bucket_name}")
        
        # AWS 키가 없으면 S3 클라이언트를 None으로 설정
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            print("❌ AWS 환경변수가 설정되지 않았습니다!")
            print("   Airflow UI → Admin → Variables에서 다음 변수들을 설정해주세요:")
            print("   - AWS_ACCESS_KEY_ID")
            print("   - AWS_SECRET_ACCESS_KEY")
            print("   - AWS_REGION (선택사항)")
            print("   - S3_BUCKET_NAME (선택사항)")
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
            print(f"✅ S3 클라이언트 초기화 완료: {self.bucket_name}")
        except Exception as e:
            print(f"❌ S3 클라이언트 초기화 실패: {e}")
            self.s3_client = None

# DAG 정의
dag = DAG(
    'wconcept_html_to_csv_converter',
    default_args=default_args,
    description='W컨셉 HTML 파일들을 CSV로 변환하는 DAG (제품정보 + 리뷰 통합)',
    schedule_interval=None,  # 수동 실행 또는 트리거로만 실행
    max_active_runs=1,
    tags=['conversion', 'wconcept', 'html', 'csv', 'ecommerce']
)

def find_html_files(base_html_dir='/home/tjddml/w/html', **context):
    """HTML 파일들을 찾아서 리스트를 반환합니다."""
    print(f"\n{'='*50}")
    print(f"🔍 HTML 파일 검색 시작: {base_html_dir}")
    print(f"{'='*50}")
    
    try:
        if not os.path.exists(base_html_dir):
            print(f"❌ HTML 디렉토리가 존재하지 않습니다: {base_html_dir}")
            context['task_instance'].xcom_push(key='html_files', value=[])
            return []
        
        # 모든 하위 디렉토리에서 HTML 파일들을 찾기
        html_files = []
        for root, dirs, files in os.walk(base_html_dir):
            for file in files:
                if file.endswith(".html"):
                    html_files.append(os.path.join(root, file))
        
        print(f"✅ 발견된 HTML 파일: {len(html_files)}개")
        for file in html_files[:5]:  # 처음 5개만 출력
            print(f"   📄 {os.path.basename(file)}")
        if len(html_files) > 5:
            print(f"   ... 외 {len(html_files) - 5}개")
        
        context['task_instance'].xcom_push(key='html_files', value=html_files)
        context['task_instance'].xcom_push(key='base_html_dir', value=base_html_dir)
        
        return html_files
        
    except Exception as e:
        print(f"❌ HTML 파일 검색 중 오류: {e}")
        context['task_instance'].xcom_push(key='html_files', value=[])
        return []

def extract_category_from_path(file_path):
    """파일 경로에서 대분류 정보를 추출합니다."""
    try:
        # 파일 경로에서 디렉토리 구조 분석
        path_parts = file_path.split('/')
        
        # 디렉토리 이름을 대분류로 매핑 (상의/바지/원피스/스커트만)
        category_mapping = {
            '상의': ['상의', '티셔츠', '셔츠', '블라우스', '니트', '스웨터', '후드', '상의류'],
            '바지': ['바지', '팬츠', '데님', '슬랙스', '조거', '바지류'],
            '원피스': ['원피스', '드레스', '원피스류'],
            '스커트': ['스커트', '치마', '스커트류']
        }
        
        # 경로의 각 부분을 확인하여 대분류 매핑
        for part in path_parts:
            part_lower = part.lower()
            for category, keywords in category_mapping.items():
                for keyword in keywords:
                    if keyword in part_lower:
                        return category
        
        return None
        
    except Exception as e:
        print(f"⚠️ 경로에서 대분류 추출 실패: {e}")
        return None

def parse_html_file(file_path):
    """단일 HTML 파일을 파싱하여 상품 정보와 리뷰를 추출합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            full_text = soup.get_text(separator="\n")

        product_id = os.path.basename(file_path).replace(".html", "")
        
        # === 제품 정보 추출 ===
        # 기본 정보 추출
        product_name = soup.title.text.strip().replace('[', '').replace(']', '') if soup.title else None
        canonical = soup.find("link", rel="canonical")
        product_link = canonical["href"] if canonical else None

        # 브랜드 정보 추출
        brand = seller = None
        brand_script = soup.find("script", string=lambda s: s and "ep_page_brandNM" in s)
        if brand_script:
            for line in brand_script.string.splitlines():
                if "ep_page_brandNM" in line:
                    brand = line.split("=")[-1].strip().strip('"+; ')
                    seller = brand

        # 가격 정보 추출
        price_wrap = soup.find("div", class_="price_wrap")
        normal_price = discount_price = None
        if price_wrap:
            # 디버깅: 가격 정보 HTML 구조 출력 (처음 5개 파일만)
            if product_id in ['debug_sample']:  # 실제 디버깅이 필요할 때 사용
                print(f"🔍 가격 정보 HTML 구조 ({product_id}):")
                print(price_wrap.prettify()[:1000])  # 처음 1000자만 출력
            
            # 모든 dd 태그를 찾아서 가격 정보 추출
            dd_tags = price_wrap.find_all("dd")
            
            for dd_tag in dd_tags:
                # dd 태그 내부의 em 태그 찾기
                em_tag = dd_tag.find("em")
                if em_tag:
                    price_text = em_tag.text.strip().replace(",", "")
                    
                    # dd 태그의 클래스에 따라 구분
                    dd_class = dd_tag.get("class", [])
                    
                    if "normal" in dd_class:
                        normal_price = price_text
                    elif "cupon" in dd_class:
                        discount_price = price_text
                    else:
                        # 클래스가 없는 경우, 첫 번째 dd 태그를 정상가로 간주
                        if normal_price is None:
                            normal_price = price_text
                        elif discount_price is None:
                            discount_price = price_text
            
            # em 태그가 없는 경우를 위한 대체 방법
            if normal_price is None:
                # 정상가를 찾지 못한 경우, 모든 dd 태그에서 숫자 추출 시도
                for dd_tag in dd_tags:
                    dd_class = dd_tag.get("class", [])
                    if "normal" in dd_class or (not dd_class and normal_price is None):
                        text = dd_tag.get_text(strip=True)
                        price_match = re.search(r'[\d,]+', text)
                        if price_match:
                            normal_price = price_match.group().replace(",", "")
                            break
            
            if discount_price is None:
                # 할인가를 찾지 못한 경우, cupon 클래스가 있는 dd 태그에서 숫자 추출 시도
                for dd_tag in dd_tags:
                    dd_class = dd_tag.get("class", [])
                    if "cupon" in dd_class:
                        text = dd_tag.get_text(strip=True)
                        price_match = re.search(r'[\d,]+', text)
                        if price_match:
                            discount_price = price_match.group().replace(",", "")
                            break

        # 상품 ID 추출
        product_id_from_script = None
        id_script = soup.find("script", string=lambda s: s and "prodid" in s)
        if id_script:
            match = re.search(r"['\"]prodid['\"]\s*:\s*['\"]?(\d+)", id_script.string)
            if match:
                product_id_from_script = match.group(1)

        # 성별 정보 추출
        gender_tag = soup.select_one("#prdLocaiton li:nth-of-type(2) a")
        gender = gender_tag.get_text(strip=True) if gender_tag else None

        # 카테고리 정보 추출
        main_category = soup.select_one("#cateDepth3 > button")
        sub_category = soup.select_one("#btn4depth")
        product_main_category = main_category.get_text(strip=True) if main_category else None
        product_sub_category = sub_category.get_text(strip=True) if sub_category else None
        
        # 디렉토리 이름에서 대분류 추출 (파일 경로 기반)
        directory_category = extract_category_from_path(file_path)
        
        # 디렉토리에서 추출한 대분류가 있으면 우선 사용
        if directory_category:
            product_main_category = directory_category

        # 좋아요 수 추출
        like_tag = soup.find(id="myHeartAllCount")
        like_count = like_tag.get_text(strip=True) if like_tag else None

        # 이미지 URL 추출 (다운로드 없이 URL만 저장)
        image_url = None
        og_image = soup.find("meta", property="og:image")
        if og_image:
            image_url = og_image["content"]

        # 사이즈 정보 추출
        size_info = { "사이즈": None, "총장": None, "어깨 너비": None, "가슴 단면": None, "소매 길이": None }
        product_material = product_color = product_care = product_code = product_dimension = None

        tables = soup.find_all("table")
        for table in tables:
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    key = cells[0].text.strip()
                    value = cells[1].text.strip()
                    for k in size_info:
                        if k in key and not size_info[k]:
                            size_info[k] = value
                    if "상품코드" in key and not product_code:
                        product_code = value
                    elif ("치수" in key or "크기" in key) and not product_dimension:
                        product_dimension = value

        # 상품 상세 정보 추출
        material_tag = soup.select_one("#container > div > div > div:nth-of-type(1) > div:nth-of-type(2) > dl > dd > ul > li:nth-of-type(2)")
        if material_tag:
            product_material = material_tag.get_text(strip=True)

        color_tag = soup.select_one("#container > div > div > div:nth-of-type(3) > div:nth-of-type(4) > table > tbody > tr:nth-of-type(2) > td")
        if color_tag:
            product_color = color_tag.get_text(strip=True)

        care_tag = soup.select_one("#container > div > div > div:nth-of-type(3) > div:nth-of-type(4) > table > tbody > tr:nth-of-type(6) > td")
        if care_tag:
            product_care = care_tag.get_text(strip=True)

        # === 리뷰 정보 추출 ===
        def get_text(sel):
            tag = soup.select_one(sel)
            return tag.get_text(strip=True) if tag else None

        리뷰개수 = get_text("#reviewCnt3")
        리뷰평균 = get_text("#container div div div:nth-of-type(4) > div:nth-of-type(1) > div > div:nth-of-type(1) div div:nth-of-type(2) > strong")

        # 리뷰 row 반복
        reviews = []
        rows = soup.select("#reviewList table tbody tr")
        for row in rows:
            def get_text_from(tag, sel):
                el = tag.select_one(sel)
                return el.get_text(strip=True) if el else None

            def get_attr_from(tag, sel, attr):
                el = tag.select_one(sel)
                return el.get(attr) if el and el.has_attr(attr) else None

            def get_date_from_row(tag):
                p_tag = tag.select_one("td:nth-of-type(2) > div:nth-of-type(1) > p")
                if p_tag:
                    span = p_tag.select_one("span")
                    if span:
                        return span.get_text(strip=True)
                return None

            def get_writer_info(tag):
                """작성자 정보를 종합적으로 추출"""
                writer_name = get_text_from(tag, "td:nth-of-type(2) div:nth-of-type(1) p em")
                size_info = get_text_from(tag, "td:nth-of-type(2) div:nth-of-type(1) div div p:nth-of-type(2) span")
                
                info_parts = []
                if writer_name:
                    info_parts.append(f"작성자: {writer_name}")
                if size_info:
                    info_parts.append(f"사이즈: {size_info}")
                    
                return " | ".join(info_parts) if info_parts else None

            리뷰 = {
                "상품코드": product_id,
                "작성자명": get_text_from(row, "td:nth-of-type(2) div:nth-of-type(1) p em"),
                "리뷰갯수": 리뷰개수,
                "평균평점": 리뷰평균,
                "작성날짜": get_date_from_row(row),
                "구매옵션": get_text_from(row, "td:nth-of-type(2) div:nth-of-type(1) div div p span"),
                "리뷰내용": get_text_from(row, "td:nth-of-type(2) div:nth-of-type(2) p"),
                "리뷰 이미지 url": get_attr_from(row, "td:nth-of-type(2) ul li img", "src"),
                "작성자 정보": get_writer_info(row)
            }

            # 내용이 존재하는 row만 추가
            if 리뷰["리뷰내용"] or 리뷰["작성자명"]:
                reviews.append(리뷰)

        # 제품 정보 반환
        product_info = {
            "상품코드": product_id,
            "상품명": product_name,
            "브랜드명": brand,
            "대분류": product_main_category,
            "소분류": product_sub_category,
            "원가": normal_price,
            "할인가": discount_price,
            "성별": gender,
            "이미지URL": image_url,
            "소재": product_material,
            "색상": product_color,
            "좋아요수": like_count,
            "상품링크": product_link
        }

        return {
            "product_info": product_info,
            "reviews": reviews
        }
        
    except Exception as e:
        print(f"❌ HTML 파일 파싱 중 오류 ({os.path.basename(file_path)}): {e}")
        return None

def convert_html_to_csv(base_html_dir='/home/tjddml/w/html', **context):
    """HTML 파일들을 CSV로 변환합니다 (제품정보 + 리뷰 통합)."""
    print(f"\n{'='*50}")
    print(f"🔄 HTML to CSV 변환 시작: {base_html_dir}")
    print(f"{'='*50}")
    
    try:
        # 출력 경로 설정 (HTML 디렉토리와 같은 레벨에 저장)
        output_dir = os.path.dirname(base_html_dir)
        products_csv_path = os.path.join(output_dir, "parsed_products.csv")
        reviews_csv_path = os.path.join(output_dir, "reviews_extracted.csv")
        
        # HTML 파일 리스트 가져오기
        html_files = context['task_instance'].xcom_pull(task_ids='find_html_files', key='html_files')
        
        if not html_files:
            print("❌ 처리할 HTML 파일이 없습니다.")
            return False
        
        print(f"📊 총 {len(html_files)}개 HTML 파일 처리 시작...")
        
        products_results = []
        reviews_results = []
        success_count = 0
        error_count = 0
        
        for idx, file_path in enumerate(html_files, 1):
            try:
                result = parse_html_file(file_path)
                if result:
                    # 제품 정보 추가
                    if result["product_info"]["상품명"]:  # 상품명이 있는 경우만 추가
                        products_results.append(result["product_info"])
                    
                    # 리뷰 정보 추가
                    reviews_results.extend(result["reviews"])
                    
                    success_count += 1
                else:
                    error_count += 1
                    
                # 1000개 단위로 진행 상황 출력
                if idx % 1000 == 0:
                    print(f"   📈 {idx}개 처리 완료 (성공: {success_count}, 실패: {error_count})")
                    
            except Exception as e:
                print(f"❌ 파일 처리 중 오류 ({os.path.basename(file_path)}): {e}")
                error_count += 1
        
        # CSV 저장
        if products_results or reviews_results:
            # 제품 정보 CSV 저장
            if products_results:
                df_products = pd.DataFrame(products_results)
                df_products.to_csv(products_csv_path, index=False, encoding="utf-8-sig")
                print(f"📦 제품 정보 CSV 저장 완료: {len(products_results)}개")
            
            # 리뷰 정보 CSV 저장
            if reviews_results:
                df_reviews = pd.DataFrame(reviews_results)
                df_reviews.to_csv(reviews_csv_path, index=False, encoding="utf-8-sig")
                print(f"📝 리뷰 정보 CSV 저장 완료: {len(reviews_results)}개")
            
            print(f"\n✅ CSV 변환 완료!")
            print(f"📊 총 처리: {len(html_files)}개")
            print(f"✅ 성공: {success_count}개")
            print(f"❌ 실패: {error_count}개")
            print(f"📈 성공률: {(success_count/len(html_files)*100):.1f}%")
            print(f"📦 제품 정보: {len(products_results)}개")
            print(f"📝 리뷰 정보: {len(reviews_results)}개")
            print(f"📁 제품 CSV 경로: {products_csv_path}")
            print(f"📁 리뷰 CSV 경로: {reviews_csv_path}")
            
            # 결과를 XCom에 저장
            context['task_instance'].xcom_push(key='products_csv_path', value=products_csv_path)
            context['task_instance'].xcom_push(key='reviews_csv_path', value=reviews_csv_path)
            context['task_instance'].xcom_push(key='total_processed', value=len(html_files))
            context['task_instance'].xcom_push(key='success_count', value=success_count)
            context['task_instance'].xcom_push(key='error_count', value=error_count)
            context['task_instance'].xcom_push(key='total_products', value=len(products_results))
            context['task_instance'].xcom_push(key='total_reviews', value=len(reviews_results))
            
            return True
        else:
            print("❌ 저장할 결과가 없습니다.")
            return False
            
    except Exception as e:
        print(f"❌ CSV 변환 중 오류: {e}")
        return False

def conversion_summary(**context):
    """변환 작업 요약을 출력합니다."""
    print(f"\n{'='*50}")
    print(f"📋 HTML to CSV 변환 작업 요약")
    print(f"{'='*50}")
    
    try:
        products_csv_path = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='products_csv_path')
        reviews_csv_path = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='reviews_csv_path')
        total_processed = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='total_processed')
        success_count = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='success_count')
        error_count = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='error_count')
        total_products = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='total_products')
        total_reviews = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='total_reviews')
        s3_upload_results = context['task_instance'].xcom_pull(task_ids='upload_to_s3', key='s3_upload_results')
        
        if total_processed is not None:
            print(f"🎉 HTML to CSV 변환 완료!")
            print(f"📊 총 처리된 파일: {total_processed}개")
            print(f"✅ 성공: {success_count}개")
            print(f"❌ 실패: {error_count}개")
            print(f"📦 추출된 제품: {total_products}개")
            print(f"📝 추출된 리뷰: {total_reviews}개")
            if products_csv_path:
                print(f"📁 제품 CSV 파일 경로: {products_csv_path}")
            if reviews_csv_path:
                print(f"📁 리뷰 CSV 파일 경로: {reviews_csv_path}")
            
            if s3_upload_results:
                print(f"\n☁️ S3 업로드 결과:")
                for key, path in s3_upload_results.items():
                    if key == 'html_files':
                        print(f"   {key}: {path} (HTML 파일들)")
                    else:
                        print(f"   {key}: {path}")
        else:
            print("❌ 변환 결과를 찾을 수 없습니다.")
        
        print("="*50)
        return True
        
    except Exception as e:
        print(f"❌ 요약 생성 중 오류: {e}")
        return True

def upload_to_s3_task(**context):
    """CSV 파일들과 HTML 파일들을 S3에 업로드"""
    products_csv_path = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='products_csv_path')
    reviews_csv_path = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='reviews_csv_path')
    total_products = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='total_products')
    total_reviews = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='total_reviews')
    base_html_dir = context['task_instance'].xcom_pull(task_ids='find_html_files', key='base_html_dir')
    
    if not products_csv_path and not reviews_csv_path:
        print("❌ 업로드할 CSV 파일이 없습니다.")
        return False
    
    # S3 업로더 초기화
    s3_uploader = S3Uploader()
    
    if not s3_uploader.s3_client:
        print("❌ S3 클라이언트가 초기화되지 않았습니다.")
        return False
    
    today = datetime.now().strftime('%Y-%m-%d')
    upload_results = {}
    
    try:
        # 제품 정보 CSV 업로드
        if products_csv_path and os.path.exists(products_csv_path):
            filename = os.path.basename(products_csv_path)
            s3_key = f"wconcept_csvs/{today}/{filename}"
            
            print(f"🔄 제품 정보 CSV 업로드 중: {products_csv_path} → s3://{s3_uploader.bucket_name}/{s3_key}")
            
            s3_uploader.s3_client.upload_file(
                products_csv_path,
                s3_uploader.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'text/csv'}
            )
            
            upload_results['product_csv'] = f"s3://{s3_uploader.bucket_name}/{s3_key}"
            print(f"✅ 제품 정보 CSV S3 업로드 완료: {total_products}개 제품")
        
        # 리뷰 정보 CSV 업로드
        if reviews_csv_path and os.path.exists(reviews_csv_path):
            filename = os.path.basename(reviews_csv_path)
            s3_key = f"wconcept_csvs/{today}/{filename}"
            
            print(f"🔄 리뷰 정보 CSV 업로드 중: {reviews_csv_path} → s3://{s3_uploader.bucket_name}/{s3_key}")
            
            s3_uploader.s3_client.upload_file(
                reviews_csv_path,
                s3_uploader.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'text/csv'}
            )
            
            upload_results['review_csv'] = f"s3://{s3_uploader.bucket_name}/{s3_key}"
            print(f"✅ 리뷰 정보 CSV S3 업로드 완료: {total_reviews}개 리뷰")
        
        # HTML 파일들 S3 업로드
        if base_html_dir and os.path.exists(base_html_dir):
            print(f"\n🔄 HTML 파일들 S3 업로드 시작: {base_html_dir}")
            html_upload_count = 0
            
            for root, dirs, files in os.walk(base_html_dir):
                for file in files:
                    if file.endswith('.html'):
                        local_file_path = os.path.join(root, file)
                        
                        # 상대 경로 계산 (base_html_dir 기준)
                        relative_path = os.path.relpath(local_file_path, base_html_dir)
                        s3_key = f"wconcept_htmls/{today}/{relative_path}"
                        
                        try:
                            s3_uploader.s3_client.upload_file(
                                local_file_path,
                                s3_uploader.bucket_name,
                                s3_key,
                                ExtraArgs={'ContentType': 'text/html'}
                            )
                            html_upload_count += 1
                            
                            if html_upload_count % 100 == 0:
                                print(f"   📈 {html_upload_count}개 HTML 파일 업로드 완료")
                                
                        except Exception as e:
                            print(f"   ❌ HTML 파일 업로드 실패: {file} - {e}")
            
            upload_results['html_files'] = f"s3://{s3_uploader.bucket_name}/wconcept_htmls/{today}/"
            print(f"✅ HTML 파일들 S3 업로드 완료: {html_upload_count}개 파일")
        
        # 업로드 결과를 XCom에 저장
        context['task_instance'].xcom_push(key='s3_upload_results', value=upload_results)
        return True
        
    except Exception as e:
        print(f"❌ S3 업로드 실패: {e}")
        return False

def cleanup_html_files_task(**context):
    """S3 업로드 성공 후 로컬 HTML/CSV 파일 정리"""
    base_html_dir = context['task_instance'].xcom_pull(task_ids='find_html_files', key='base_html_dir')
    s3_upload_results = context['task_instance'].xcom_pull(task_ids='upload_to_s3', key='s3_upload_results')
    products_csv_path = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='products_csv_path')
    reviews_csv_path = context['task_instance'].xcom_pull(task_ids='convert_html_to_csv', key='reviews_csv_path')

    # S3 업로드가 성공한 경우에만 정리
    if not s3_upload_results:
        print("❌ S3 업로드가 성공하지 않아 로컬 파일을 정리하지 않습니다.")
        return False

    # 1) HTML 파일 및 디렉토리 정리
    if not base_html_dir or not os.path.exists(base_html_dir):
        print(f"⚠️ HTML 디렉토리가 존재하지 않음: {base_html_dir}")
    else:
        print(f"\n🗑️ HTML 파일들 정리 시작: {base_html_dir}")
        total_deleted_html = 0

        # 모든 하위 디렉토리에서 HTML 파일 삭제
        for root, dirs, files in os.walk(base_html_dir, topdown=False):
            for file in files:
                if file.endswith('.html'):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        total_deleted_html += 1
                    except Exception as e:
                        print(f"     ❌ 삭제 실패: {file} - {e}")

            # 빈 디렉토리 삭제 (root 디렉토리 제외)
            if root != base_html_dir:
                try:
                    if not os.listdir(root):
                        os.rmdir(root)
                        print(f"     ✅ 빈 디렉토리 삭제: {root}")
                except Exception as e:
                    print(f"     ⚠️ 디렉토리 삭제 실패: {root} - {e}")

        # 전체 HTML 디렉토리가 비어있으면 삭제
        try:
            if not os.listdir(base_html_dir):
                os.rmdir(base_html_dir)
                print(f"   ✅ 전체 HTML 디렉토리 삭제: {base_html_dir}")
        except Exception as e:
            print(f"   ⚠️ 전체 디렉토리 삭제 실패: {base_html_dir} - {e}")

        print(f"📊 HTML 파일 정리 완료: {total_deleted_html}개 파일 삭제")

    # 2) 변환된 CSV 파일 정리 (제품/리뷰)
    total_deleted_csv = 0
    for csv_path, label in [
        (products_csv_path, '제품 CSV'),
        (reviews_csv_path, '리뷰 CSV'),
    ]:
        if csv_path and os.path.exists(csv_path):
            try:
                os.remove(csv_path)
                total_deleted_csv += 1
                print(f"✅ 삭제 완료: {label} - {csv_path}")
            except Exception as e:
                print(f"❌ 삭제 실패: {label} - {csv_path} | {e}")

    if total_deleted_csv == 0:
        print("ℹ️ 삭제할 로컬 CSV 파일이 없습니다.")
    else:
        print(f"📊 CSV 파일 정리 완료: {total_deleted_csv}개 파일 삭제")

    return True

# 태스크 정의
start_task = DummyOperator(
    task_id='start_html_to_csv_conversion',
    dag=dag
)

find_html_task = PythonOperator(
    task_id='find_html_files',
    python_callable=find_html_files,
    op_kwargs={
        'base_html_dir': '/home/tjddml/w/html'  # HTML 크롤러 DAG의 출력 경로
    },
    dag=dag
)

convert_task = PythonOperator(
    task_id='convert_html_to_csv',
    python_callable=convert_html_to_csv,
    op_kwargs={
        'base_html_dir': '/home/tjddml/w/html'  # HTML 크롤러 DAG의 출력 경로
    },
    dag=dag
)

summary_task = PythonOperator(
    task_id='conversion_summary',
    python_callable=conversion_summary,
    dag=dag
)

# S3에 업로드
upload_task = PythonOperator(
    task_id='upload_to_s3',
    python_callable=upload_to_s3_task,
    dag=dag
)

# HTML 파일 정리
cleanup_task = PythonOperator(
    task_id='cleanup_html_files',
    python_callable=cleanup_html_files_task,
    dag=dag
)

# 다음 DAG 트리거 (29cm step1)
trigger_step1 = TriggerDagRunOperator(
    task_id="trigger_step1_link_collector",
    trigger_dag_id="step1_link_collector",
    wait_for_completion=False,
    conf={"triggered_by": "wconcept_html_to_csv_converter"},
)

# 태스크 의존성 설정 (S3 업로드 및 HTML 정리 포함)
start_task >> find_html_task >> convert_task >> upload_task >> cleanup_task >> summary_task >> trigger_step1
