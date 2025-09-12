from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import os
import json
import re
import pandas as pd
from bs4 import BeautifulSoup
import boto3
from botocore.exceptions import ClientError
import re

# DAG 기본 설정
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 8, 5),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
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

def normalize_musinsa_image_url(url):
    """
    무신사 이미지 URL을 올바른 형태로 정규화합니다.
    https:/images/goods_img/... → https://image.msscdn.net/thumbnails/images/goods_img/..._big.jpg
    """
    if not url:
        return None
    
    url = str(url).strip()
    
    # 이미 올바른 형태라면 그대로 반환
    if url.startswith('https://image.msscdn.net/thumbnails/images/goods_img/'):
        return url
    
    # https:/images/goods_img/ 형태를 정규화
    if url.startswith('https:/images/goods_img/'):
        url = url.replace('https:/images/goods_img/', 'https://image.msscdn.net/thumbnails/images/goods_img/')
    
    # https://images/goods_img/ 형태를 정규화
    elif url.startswith('https://images/goods_img/'):
        url = url.replace('https://images/goods_img/', 'https://image.msscdn.net/thumbnails/images/goods_img/')
    
    # 상대 경로인 경우
    elif url.startswith('/images/goods_img/'):
        url = 'https://image.msscdn.net/thumbnails/images/goods_img/' + url[18:]
    
    # 파일명 접미사 통일 (_500, _1000, _org 등 → _big)
    if '_500.' in url or '_1000.' in url or '_org.' in url:
        url = re.sub(r'_(500|1000|org)\.(jpg|jpeg|png)$', r'_big.\2', url, flags=re.IGNORECASE)
    
    # _big 접미사가 없으면 추가
    if not re.search(r'_big\.(jpg|jpeg|png)$', url, flags=re.IGNORECASE):
        url = re.sub(r'\.(jpg|jpeg|png)$', r'_big.\1', url, flags=re.IGNORECASE)
    
    return url

def extract_notice_info(html_content):
    """상품 고시 정보 추출 (제품소재, 색상)"""
    soup = BeautifulSoup(html_content, 'html.parser')
    info = {"제품소재": None, "색상": None}
    
    # 방법 1: h3 태그에서 "상품 고시" 찾기
    dl = None
    for h3 in soup.find_all("h3"):
        if "상품 고시" in h3.get_text():
            dl = h3.find_next("dl")
            break
    
    # 방법 2: dl 태그 직접 찾기
    if not dl:
        dl = soup.find("dl")
    
    if dl:
        items = list(dl.find_all(["dt", "dd"]))
        for i in range(0, len(items)-1, 2):
            key = items[i].get_text(strip=True)
            val = items[i+1].get_text(strip=True)
            if "소재" in key and not info["제품소재"]:
                info["제품소재"] = val
            if "색상" in key and not info["색상"]:
                info["색상"] = val
    else:
        # 방법 3: table에서 찾기
        table = None
        for th in soup.find_all(['th', 'td']):
            txt = th.get_text(strip=True)
            if "상품 고시" in txt or "상품정보제공고시" in txt:
                table = th.find_parent('table')
                break
        
        if table:
            for row in table.find_all('tr'):
                tds = row.find_all(['th', 'td'])
                if len(tds) >= 2:
                    key = tds[0].get_text(strip=True)
                    val = tds[1].get_text(strip=True)
                    if "소재" in key and not info["제품소재"]:
                        info["제품소재"] = val
                    if "색상" in key and not info["색상"]:
                        info["색상"] = val
    
    return info

def extract_likes_from_html(soup):
    """좋아요 수 추출"""
    try:
        like_span = soup.select_one("div.sc-16dm5t2-0.jnCysi > div > span")
        if like_span:
            return like_span.get_text(strip=True)
    except:
        pass
    return None

def extract_product_reviews(html_content, product_no, product_info=None):
    """HTML에서 리뷰 데이터 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    reviews = []
    
    # 상품 정보에서 리뷰 갯수와 평균 평점 가져오기
    total_review_count = product_info.get('총 리뷰갯수') if product_info else None
    avg_rating = product_info.get('평균 평점') if product_info else None
    
    review_blocks = soup.select("div.review-list-item__Container-sc-13zantg-0")
    for block in review_blocks:
        nickname_tag = block.select_one("span.UserProfileSection__Nickname-sc-12rrbzu-4")
        nickname = nickname_tag.get_text(strip=True) if nickname_tag else None
        
        date_tag = block.select_one("span.UserProfileSection__PurchaseDate-sc-12rrbzu-5")
        date = date_tag.get_text(strip=True) if date_tag else None
        
        rating_tag = block.select_one("div.StarsScore__Container-sc-1qjm0n5-0 span.text-body_13px_semi")
        rating = rating_tag.get_text(strip=True) if rating_tag else None

        user_info_tag = block.select_one("div.UserInfoGoodsOptionSection__UserInfoGoodsOption-sc-1p4ukac-1 span")
        user_info = user_info_tag.get_text(strip=True) if user_info_tag else None

        purchase_option_tag = block.select_one("div.UserInfoGoodsOptionSection__UserInfoGoodsOption-sc-1p4ukac-1 span:nth-child(3)")
        purchase_option = purchase_option_tag.get_text(strip=True) if purchase_option_tag else None

        content_tag = block.select_one("div.ExpandableContent__ContentContainer-sc-gj5b23-1 span.text-body_13px_reg.text-black")
        content = content_tag.get_text(strip=True) if content_tag else None

        img_tag = block.select_one("div.ExpandableImageGroup__Container-sc-uvnh0q-0 img")
        img_url = normalize_musinsa_image_url(img_tag['src']) if img_tag else None

        # 리뷰 내용 정리 (줄바꿈 제거)
        if content:
            content = content.replace('\n', ' ').replace('\r', ' ').strip()

        reviews.append({
            '제품번호': product_no,
            '작성자명': nickname,
            '리뷰갯수': total_review_count,
            '평균평점': avg_rating,
            '작성날짜': date,
            '구매옵션': purchase_option,
            '리뷰내용': content,
            '리뷰이미지URL': img_url,
            '작성자정보': user_info,
        })

    return reviews

def extract_data_from_html(html_content):
    """HTML에서 상품 데이터 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # JSON 데이터 추출
    script_tag = soup.find('script', id='pdp-data')
    if not script_tag:
        return None
    
    script_text = script_tag.string
    match = re.search(r'window\.__MSS__\.product\.state\s*=\s*(\{.*?\});', script_text, re.S)
    if not match:
        return None
    
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 오류: {e}")
        return None
    
    # 상품 정보 추출
    product_info = {
        '제품번호': data.get('goodsNo'),
        '제품이름': data.get('goodsNm'),
        '제품대분류': data.get('category', {}).get('categoryDepth1Name'),
        '제품소분류': data.get('category', {}).get('categoryDepth2Name'),
        '원가': data.get('goodsPrice', {}).get('normalPrice'),
        '할인가': data.get('goodsPrice', {}).get('salePrice'),
        '사진': normalize_musinsa_image_url(data.get('thumbnailImageUrl', '')) if data.get('thumbnailImageUrl') else '',
        '브랜드': data.get('brandInfo', {}).get('brandName'),
        '성별': data.get('sex'),
        '총 리뷰갯수': data.get('goodsReview', {}).get('totalCount'),
        '평균 평점': data.get('goodsReview', {}).get('satisfactionScore'),
        '좋아요': data.get('wishCount'),
    }

    # 좋아요 수가 없으면 HTML에서 직접 추출
    if not product_info['좋아요']:
        product_info['좋아요'] = extract_likes_from_html(soup)

    # 상품 고시 정보 추가
    notice_info = extract_notice_info(html_content)
    product_info.update(notice_info)
    
    return product_info

def process_html_files(folder_path):
    """폴더 내 HTML 파일들을 처리하여 상품 정보와 리뷰 정보 반환"""
    if not os.path.exists(folder_path):
        print(f"❌ 폴더가 존재하지 않습니다: {folder_path}")
        return [], []
    
    html_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.html')]
    
    if not html_files:
        print(f"⚠️ {folder_path}에 HTML 파일이 없습니다.")
        return [], []
    
    print(f"🔄 {folder_path}에서 {len(html_files)}개 HTML 파일 처리 중...")
    
    all_product_info = []
    all_reviews = []
    
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as file:
                html_content = file.read()
            
            # 상품 정보 추출
            product_data = extract_data_from_html(html_content)
            if product_data:
                all_product_info.append(product_data)
                
                # 리뷰 정보 추출
                if product_data.get('제품번호'):
                    reviews = extract_product_reviews(html_content, product_data['제품번호'], product_data)
                    all_reviews.extend(reviews)
                    print(f"✅ {os.path.basename(html_file)} 처리 완료 (상품: 1개, 리뷰: {len(reviews)}개)")
                else:
                    print(f"✅ {os.path.basename(html_file)} 처리 완료 (상품: 1개, 리뷰: 0개)")
            else:
                print(f"⚠️ {os.path.basename(html_file)} 데이터 추출 실패")
                
        except Exception as e:
            print(f"❌ {os.path.basename(html_file)} 처리 오류: {e}")

    return all_product_info, all_reviews

def convert_html_to_csv_task(**context):
    """HTML 파일들을 CSV로 변환하는 메인 태스크"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 작업 디렉토리 설정
    work_dir = f"/home/tjddml/musinsa_csv_converter/{today}"
    os.makedirs(work_dir, exist_ok=True)
    
    # HTML 파일 디렉토리
    html_base_dir = f"/home/tjddml/musinsa_htmls/{today}"
    
    if not os.path.exists(html_base_dir):
        print(f"❌ HTML 디렉토리가 존재하지 않습니다: {html_base_dir}")
        print("   크롤링 DAG가 정상적으로 실행되었는지 확인해주세요.")
        return
    
    # 카테고리별 처리
    categories = ['top', 'bottom']
    all_product_data = []
    all_review_data = []
    
    for category in categories:
        print(f"\n{'='*30}")
        print(f"🔄 {category} 카테고리 처리 시작")
        print(f"{'='*30}")
        
        category_html_dir = os.path.join(html_base_dir, category)
        
        if os.path.exists(category_html_dir):
            # HTML 파일 처리
            product_info, reviews = process_html_files(category_html_dir)
            
            # 카테고리 정보 추가
            for product in product_info:
                product['카테고리'] = category
            for review in reviews:
                review['카테고리'] = category
            
            all_product_data.extend(product_info)
            all_review_data.extend(reviews)
            
            print(f"✅ {category} 카테고리 처리 완료: 상품 {len(product_info)}개, 리뷰 {len(reviews)}개")
        else:
            print(f"⚠️ {category} 카테고리 HTML 디렉토리가 존재하지 않습니다: {category_html_dir}")
    
    # 상품 정보 CSV 저장
    final_product_csv = None
    if all_product_data:
        df_products = pd.DataFrame(all_product_data)
        
        # 상품링크 컬럼 추가
        df_products['상품링크'] = 'https://www.musinsa.com/products/' + df_products['제품번호'].astype(str)
        
        # 컬럼명 변경 및 순서 조정
        column_mapping = {
            '제품번호': '상품코드',
            '제품이름': '상품명',
            '브랜드': '브랜드명',
            '제품대분류': '대분류',
            '제품소분류': '소분류',
            '원가': '원가',
            '할인가': '할인가',
            '성별': '성별',
            '사진': '이미지url',
            '제품소재': '소재',
            '색상': '색상',
            '좋아요': '좋아요 수',
            '상품링크': '상품링크',
        }
        
        # 원하는 순서로 칼럼 재배열
        desired_columns = [
            '상품코드', '상품명', '브랜드명', '대분류', '소분류',
            '원가', '할인가', '성별', '이미지url', '소재',
            '색상', '좋아요 수', '상품링크'
        ]
        
        # 칼럼명 변경
        df_products = df_products.rename(columns=column_mapping)
        
        # 원하는 순서로 칼럼 선택
        available_columns = [col for col in desired_columns if col in df_products.columns]
        df_products = df_products[available_columns]
        
        # CSV 저장 (시간별 구분)
        current_time = datetime.now().strftime('%H%M')
        final_product_csv = os.path.join(work_dir, f'product_info_{current_time}.csv')
        df_products.to_csv(final_product_csv, index=False, encoding='utf-8-sig')
        
        print(f"✅ 상품 정보 CSV 저장 완료: {len(df_products)}개 제품 -> {final_product_csv}")
    
    # 리뷰 정보 CSV 저장
    final_review_csv = None
    if all_review_data:
        df_reviews = pd.DataFrame(all_review_data)
        
        # 리뷰 칼럼 순서 조정
        desired_review_columns = [
            '제품번호', '작성자명', '리뷰갯수', '평균평점', '작성날짜', 
            '구매옵션', '리뷰내용', '리뷰이미지URL', '작성자정보'
        ]
        
        # 존재하는 칼럼만 선택하여 순서 조정
        available_review_columns = [col for col in desired_review_columns if col in df_reviews.columns]
        df_reviews = df_reviews[available_review_columns]
        
        # CSV 저장 (시간별 구분)
        current_time = datetime.now().strftime('%H%M')
        final_review_csv = os.path.join(work_dir, f'reviews_{current_time}.csv')
        df_reviews.to_csv(final_review_csv, index=False, encoding='utf-8-sig')
        
        print(f"✅ 리뷰 정보 CSV 저장 완료: {len(df_reviews)}개 리뷰 -> {final_review_csv}")
    
    # XCom에 결과 저장
    context['task_instance'].xcom_push(key='final_product_csv', value=final_product_csv)
    context['task_instance'].xcom_push(key='final_review_csv', value=final_review_csv)
    context['task_instance'].xcom_push(key='total_products', value=len(all_product_data))
    context['task_instance'].xcom_push(key='total_reviews', value=len(all_review_data))
    context['task_instance'].xcom_push(key='work_dir', value=work_dir)
    context['task_instance'].xcom_push(key='html_base_dir', value=html_base_dir)

def upload_to_s3_task(**context):
    """CSV 파일들을 S3에 업로드"""
    final_product_csv = context['task_instance'].xcom_pull(key='final_product_csv')
    final_review_csv = context['task_instance'].xcom_pull(key='final_review_csv')
    total_products = context['task_instance'].xcom_pull(key='total_products')
    total_reviews = context['task_instance'].xcom_pull(key='total_reviews')
    
    if not final_product_csv and not final_review_csv:
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
        # 상품 정보 CSV 업로드
        if final_product_csv and os.path.exists(final_product_csv):
            filename = os.path.basename(final_product_csv)
            s3_key = f"musinsa_csvs/{today}/{filename}"
            
            print(f"🔄 상품 정보 CSV 업로드 중: {final_product_csv} → s3://{s3_uploader.bucket_name}/{s3_key}")
            
            s3_uploader.s3_client.upload_file(
                final_product_csv,
                s3_uploader.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'text/csv'}
            )
            
            upload_results['product_csv'] = f"s3://{s3_uploader.bucket_name}/{s3_key}"
            print(f"✅ 상품 정보 CSV S3 업로드 완료: {total_products}개 제품")
        
        # 리뷰 정보 CSV 업로드
        if final_review_csv and os.path.exists(final_review_csv):
            filename = os.path.basename(final_review_csv)
            s3_key = f"musinsa_reviews/{today}/{filename}"
            
            print(f"🔄 리뷰 정보 CSV 업로드 중: {final_review_csv} → s3://{s3_uploader.bucket_name}/{s3_key}")
            
            s3_uploader.s3_client.upload_file(
                final_review_csv,
                s3_uploader.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'text/csv'}
            )
            
            upload_results['review_csv'] = f"s3://{s3_uploader.bucket_name}/{s3_key}"
            print(f"✅ 리뷰 정보 CSV S3 업로드 완료: {total_reviews}개 리뷰")
        
        # 업로드 결과를 XCom에 저장
        context['task_instance'].xcom_push(key='s3_upload_results', value=upload_results)
        return True
        
    except Exception as e:
        print(f"❌ S3 업로드 실패: {e}")
        return False

def cleanup_html_files_task(**context):
    """S3 업로드 성공 후 HTML 파일들 정리"""
    html_base_dir = context['task_instance'].xcom_pull(key='html_base_dir')
    s3_upload_results = context['task_instance'].xcom_pull(key='s3_upload_results')
    
    # S3 업로드가 성공한 경우에만 정리
    if not s3_upload_results:
        print("❌ S3 업로드가 성공하지 않아 HTML 파일을 정리하지 않습니다.")
        return False
    
    if not html_base_dir or not os.path.exists(html_base_dir):
        print(f"⚠️ HTML 디렉토리가 존재하지 않음: {html_base_dir}")
        return True
    
    print(f"\n🗑️ HTML 파일들 정리 시작: {html_base_dir}")
    
    categories = ['top', 'bottom']
    total_deleted = 0
    
    for category in categories:
        category_dir = os.path.join(html_base_dir, category)
        
        if not os.path.exists(category_dir):
            continue
        
        print(f"   🔄 {category} 카테고리 HTML 파일 삭제 중...")
        
        html_files = [f for f in os.listdir(category_dir) if f.endswith('.html')]
        deleted_count = 0
        
        for html_file in html_files:
            html_path = os.path.join(category_dir, html_file)
            try:
                os.remove(html_path)
                deleted_count += 1
            except Exception as e:
                print(f"     ❌ 삭제 실패: {html_file} - {e}")
        
        print(f"     ✅ {category}: {deleted_count}개 삭제 완료")
        total_deleted += deleted_count
        
        # 빈 디렉토리 삭제
        try:
            if not os.listdir(category_dir):
                os.rmdir(category_dir)
                print(f"     ✅ 빈 디렉토리 삭제: {category}")
        except Exception as e:
            print(f"     ⚠️ 디렉토리 삭제 실패: {category} - {e}")
    
    # 전체 HTML 디렉토리가 비어있으면 삭제
    try:
        if not os.listdir(html_base_dir):
            os.rmdir(html_base_dir)
            print(f"   ✅ 전체 HTML 디렉토리 삭제: {html_base_dir}")
    except Exception as e:
        print(f"   ⚠️ 전체 디렉토리 삭제 실패: {html_base_dir} - {e}")
    
    print(f"📊 HTML 파일 정리 완료: {total_deleted}개 파일 삭제")
    return True

def summary_task(**context):
    """작업 결과 요약"""
    final_product_csv = context['task_instance'].xcom_pull(key='final_product_csv')
    final_review_csv = context['task_instance'].xcom_pull(key='final_review_csv')
    total_products = context['task_instance'].xcom_pull(key='total_products')
    total_reviews = context['task_instance'].xcom_pull(key='total_reviews')
    s3_upload_results = context['task_instance'].xcom_pull(key='s3_upload_results')
    
    print(f"\n{'='*50}")
    print("📊 CSV 변환 작업 완료 요약")
    print(f"{'='*50}")
    
    if final_product_csv:
        print(f"📁 상품 정보 CSV: {final_product_csv}")
        print(f"   총 {total_products}개 제품 처리")
    
    if final_review_csv:
        print(f"📝 리뷰 정보 CSV: {final_review_csv}")
        print(f"   총 {total_reviews}개 리뷰 처리")
    
    if s3_upload_results:
        print(f"\n☁️ S3 업로드 결과:")
        for key, path in s3_upload_results.items():
            print(f"   {key}: {path}")
    
    print(f"{'='*50}")

# DAG 정의
with DAG(
    dag_id='musinsa_csv_converter_dag',
    default_args=default_args,
    description='무신사 HTML 파일을 CSV로 변환하는 DAG',
    schedule_interval=None,
    catchup=False,
    tags=['musinsa', 'csv', 'converter'],
) as dag:

    # HTML을 CSV로 변환
    convert_task = PythonOperator(
        task_id='convert_html_to_csv',
        python_callable=convert_html_to_csv_task,
        doc_md="""
        ## HTML을 CSV로 변환
        - HTML 파일에서 상품 정보와 리뷰 정보 추출
        - 카테고리별 통합 CSV 파일 생성
        """
    )

    # S3에 업로드
    upload_task = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3_task,
        doc_md="""
        ## S3 업로드
        - 생성된 CSV 파일들을 S3에 업로드
        """
    )

    # HTML 파일 정리
    cleanup_task = PythonOperator(
        task_id='cleanup_html_files',
        python_callable=cleanup_html_files_task,
        doc_md="""
        ## HTML 파일 정리
        - S3 업로드 성공 후 원본 HTML 파일들 삭제
        """
    )

    # 작업 결과 요약
    summary_task_op = PythonOperator(
        task_id='summary',
        python_callable=summary_task,
        doc_md="""
        ## 작업 결과 요약
        - 전체 변환 작업 결과 출력
        """
    )

    # W컨셉 크롤링 DAG 트리거 태스크
    trigger_wconcept_crawler = TriggerDagRunOperator(
        task_id='trigger_wconcept_crawler',
        trigger_dag_id='wconcept_product_crawling',
        wait_for_completion=False,  # 비동기 실행
        poke_interval=10,  # 10초마다 상태 확인
        allowed_states=['success'],  # 성공 상태에서만 트리거
        failed_states=['failed'],  # 실패 상태에서 트리거 안함
        dag=dag
    )

    # 태스크 의존성 설정 (W컨셉 크롤링 DAG 트리거 포함)
    convert_task >> upload_task >> cleanup_task >> summary_task_op >> trigger_wconcept_crawler