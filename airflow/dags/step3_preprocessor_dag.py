# -*- coding: utf-8 -*-
"""
step3_preprocessor_dag.py
- 제품 JSON(/json) 읽어 전처리 CSV 2종 생성
- S3 업로드:
    - JSON 원본(리뷰 제외):  s3://<bucket>/29cm_jsons/<날짜>/카테고리/<item>.json
    - 전처리 CSV:           s3://<bucket>/29cm_csvs/<날짜>/...
- 업로드 후 ./29cm_data 통째 삭제
"""
import os, json, shutil
from datetime import datetime, timedelta
import pandas as pd

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

import boto3
from botocore.exceptions import ClientError

# ===================== 경로/상수 =====================
BASE         = "./29cm_data"
JSON_DIR     = os.path.join(BASE, "json")      # 업로드(원본) 대상
REVIEWS_DIR  = os.path.join(BASE, "reviews")   # 업로드 제외
OUT_DIR_BASE = "./Complete"  # 전처리 CSV 저장 루트

# S3 프리픽스(고정)
CSV_PREFIX  = "29cm_csvs"
JSON_PREFIX = "29cm_jsons"

# 폴더 보장 (Broken DAG 예방)
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(REVIEWS_DIR, exist_ok=True)
os.makedirs(OUT_DIR_BASE, exist_ok=True)

# ===================== 유틸 =====================
def _kv(lst, title):
    for d in lst or []:
        if (d.get('itemDetailsTitles') or '').strip() == title:
            return d.get('itemDetailsValue')
    return None

def _norm_img(u: str) -> str:
    if not u: return ''
    if u.startswith('//'): return 'https:' + u
    if u.startswith('/'):  return 'https://img.29cm.co.kr' + u
    return u

def _extract_reviews(payload):
    if not payload: return []
    if isinstance(payload, dict):
        if "list" in payload and isinstance(payload["list"], list): return payload["list"]
        if "content" in payload and isinstance(payload["content"], list): return payload["content"]
        if "data" in payload: return _extract_reviews(payload["data"])
    if isinstance(payload, list): return payload
    return []

# ===================== 정규화 =====================
def normalize_product_record(obj: dict) -> dict:
    data = obj.get('data', {}) or {}
    brand = data.get('frontBrand') or {}
    details = data.get('itemDetailsList') or []
    cats = (data.get('frontCategoryInfo') or [])
    cat = cats[0] if cats else {}

    genders = {c.get('category1Name','') for c in cats}
    if any('여성' in g for g in genders): gender = '여성'
    elif any('남성' in g for g in genders): gender = '남성'
    elif genders: gender = '공용'
    else: gender = ''

    review_agg = data.get('reviewAggregation') or {}

    first_img = ''
    if isinstance(data.get('itemImages'), list) and data['itemImages']:
        first_img = _norm_img(data['itemImages'][0].get('imageUrl'))

    return {
        '제품번호': data.get('itemNo'),
        '제품이름': data.get('itemName'),
        '제품대분류': cat.get('category1Name',''),
        '제품소분류': cat.get('category3Name',''),
        '원가': data.get('consumerPrice'),
        '할인가': data.get('sellPrice'),
        '사진': first_img,
        '브랜드': brand.get('brandNameKor') or brand.get('brandNameEng',''),
        '성별': gender,
        '상품코드': data.get('itemNo'),
        '총 리뷰갯수': review_agg.get('count', 0),
        '평균 평점': review_agg.get('avgRating'),
        '제품소재': _kv(details, '제품 소재'),
        '색상': _kv(details, '색상'),
    }

def normalize_review_record(item_no: str, r: dict) -> dict:
    imgs = []
    for i in (r.get('images') or r.get('photos') or []):
        u = i.get('url') or i.get('imageUrl')
        if u: imgs.append(_norm_img(u))
    bodyinfo = []
    if r.get('height'): bodyinfo.append(f"h:{r['height']}")
    if r.get('weight'): bodyinfo.append(f"w:{r['weight']}")
    if r.get('bodyShape'): bodyinfo.append(r['bodyShape'])
    created = (r.get('createdAt') or r.get('registeredDate') or '')[:10]
    return {
        '제품번호'   : item_no,
        '작성자명'   : r.get('memberNickName') or r.get('nickname') or '',
        '작성날짜'   : created,
        '리뷰별점'   : r.get('score') or r.get('rating'),
        '사이즈'    : r.get('size') or r.get('optionSize') or '',
        '작성자정보' : ' / '.join(bodyinfo),
        '구매옵션'   : r.get('optionTitle') or r.get('optionName') or '',
        '리뷰내용'   : r.get('content') or r.get('review') or '',
        '리뷰이미지URL': ';'.join(imgs),
    }

# ===================== 전처리(main) =====================
def run_preprocess(ds=None, **_):
    date_folder = (ds or datetime.utcnow().strftime("%Y-%m-%d")).replace("-", "_")
    run_out_dir = os.path.join(OUT_DIR_BASE, date_folder)
    os.makedirs(run_out_dir, exist_ok=True)

    product_rows, review_rows = [], []

    categories = [d for d in os.listdir(JSON_DIR) if os.path.isdir(os.path.join(JSON_DIR, d))]
    for cat in categories:
        cat_json_dir = os.path.join(JSON_DIR, cat)
        for fname in os.listdir(cat_json_dir):
            if not fname.endswith(".json"): 
                continue
            item_id = os.path.splitext(fname)[0]
            with open(os.path.join(cat_json_dir, fname), "r", encoding="utf-8") as f:
                prod_obj = json.load(f)
            product_rows.append(normalize_product_record(prod_obj))

            # 리뷰 JSON은 업로드 대상에서 제외하지만, 전처리에서는 있으면 사용
            rev_dir = os.path.join(REVIEWS_DIR, cat)
            if os.path.isdir(rev_dir):
                p = 0
                while True:
                    ppath = os.path.join(rev_dir, f"{item_id}__p{p}.json")
                    if not os.path.exists(ppath): 
                        break
                    with open(ppath, "r", encoding="utf-8") as rf:
                        payload = json.load(rf)
                    for r in _extract_reviews(payload):
                        review_rows.append(normalize_review_record(item_id, r))
                    p += 1

    prod_df = pd.DataFrame(product_rows, columns=[
        '제품번호','제품이름','제품대분류','제품소분류','원가','할인가','사진','브랜드',
        '성별','상품코드','총 리뷰갯수','평균 평점','제품소재','색상'
    ])
    rev_df = pd.DataFrame(review_rows, columns=[
        '제품번호','작성자명','작성날짜','리뷰별점','사이즈','작성자정보','구매옵션','리뷰내용','리뷰이미지URL'
    ])

    prod_out = os.path.join(run_out_dir, "product_info_generalized.csv")
    rev_out  = os.path.join(run_out_dir, "review_info_generalized.csv")
    prod_df.to_csv(prod_out, index=False, encoding="utf-8-sig")
    rev_df.to_csv(rev_out,  index=False, encoding="utf-8-sig")
    print(f"[SAVE] {prod_out} ({len(prod_df)} rows)")
    print(f"[SAVE] {rev_out} ({len(rev_df)} rows)")

# ===================== S3 업로드 =====================
def _make_s3_client_from_variables():
    try:
        access_key = Variable.get("AWS_ACCESS_KEY_ID")
        secret_key = Variable.get("AWS_SECRET_ACCESS_KEY")
        region     = Variable.get("AWS_REGION", default_var="ap-northeast-2")
        return boto3.client("s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region)
    except Exception as e:
        print(f"⚠️ S3 클라이언트 초기화 실패: {e}")
        return None

def upload_to_s3(ds=None, **_):
    try:
        bucket = Variable.get("S3_BUCKET_NAME")  # 예: ivle-malle
    except Exception as e:
        print(f"⚠️ S3_BUCKET_NAME Variable 없음: {e}")
        return
    
    date_folder = (ds or datetime.utcnow().strftime("%Y-%m-%d")).replace("-", "_")

    s3 = _make_s3_client_from_variables()
    if not s3:
        print("❌ S3 클라이언트 초기화 실패로 업로드 건너뜀")
        return

    # 1) CSV 업로드: OUT_DIR_BASE/<date>/*.csv -> 29cm_csvs/<date>/
    run_out_dir = os.path.join(OUT_DIR_BASE, date_folder)
    if not os.path.isdir(run_out_dir):
        raise FileNotFoundError(f"Output dir not found: {run_out_dir}")

    csv_uploaded = 0
    for fname in os.listdir(run_out_dir):
        fpath = os.path.join(run_out_dir, fname)
        if not (os.path.isfile(fpath) and fname.lower().endswith(".csv")):
            continue
        key = f"{CSV_PREFIX}/{date_folder}/{fname}"
        s3.upload_file(fpath, bucket, key)
        print(f"[S3 CSV] s3://{bucket}/{key}")
        csv_uploaded += 1
    print(f"[S3 CSV] uploaded {csv_uploaded} file(s)")

    # 2) JSON 업로드(리뷰 제외): JSON_DIR/<cat>/*.json -> 29cm_jsons/<date>/<cat>/*.json
    json_uploaded = 0
    if os.path.isdir(JSON_DIR):
        for cat in os.listdir(JSON_DIR):
            cat_dir = os.path.join(JSON_DIR, cat)
            if not os.path.isdir(cat_dir):
                continue
            for fname in os.listdir(cat_dir):
                if not fname.endswith(".json"):
                    continue
                src = os.path.join(cat_dir, fname)
                key = f"{JSON_PREFIX}/{date_folder}/{cat}/{fname}"
                try:
                    s3.upload_file(src, bucket, key)
                    print(f"[S3 JSON] s3://{bucket}/{key}")
                    json_uploaded += 1
                except ClientError as e:
                    print(f"[S3 JSON FAIL] {src} -> {e}")
    print(f"[S3 JSON] uploaded {json_uploaded} file(s)")

# ===================== 클린업: 29cm_data 통째 삭제 =====================
def cleanup_base_folder(**_):
    base = BASE  # "./29cm_data"
    if os.path.isdir(base):
        shutil.rmtree(base, ignore_errors=True)
        print(f"[CLEANUP] Deleted folder: {base}")
    else:
        print(f"[CLEANUP] Folder not found: {base}")

# ===================== DAG 정의 =====================
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'catchup': False
}

with DAG(
    dag_id="step3_preprocessor",
    default_args=default_args,
    description="Step3: 29cm 제품 JSON 전처리 및 S3 업로드",
    schedule_interval=None,
    catchup=False,
    tags=["3_preprocess", "29cm"],
) as dag:
    t = PythonOperator(
        task_id="run_preprocess",
        python_callable=run_preprocess,
        op_kwargs={"ds": "{{ ds }}"},
    )

    upload_s3 = PythonOperator(
        task_id="upload_to_s3",
        python_callable=upload_to_s3,
        op_kwargs={"ds": "{{ ds }}"},
    )

    cleanup_task = PythonOperator(
        task_id="cleanup_base_folder",
        python_callable=cleanup_base_folder,
    )

    # ✅ 트리거는 반드시 DAG 컨텍스트(with DAG: ... 내부)에 두세요
    date_folder_template = "{{ ds | replace('-', '_') }}"

    trigger_step4 = TriggerDagRunOperator(
        task_id="trigger_step4_preprocessor",
        trigger_dag_id="step4_preprocessor",
        conf={"date_folder": date_folder_template},   # Step4가 안 써도 무해
        wait_for_completion=False,
    )

    # 의존성
    # 전처리 완료되면 → (S3 업로드와 Step4 트리거를 병렬로) → 업로드 끝나면 폴더 삭제
    t >> [upload_s3, trigger_step4]
    upload_s3 >> cleanup_task
