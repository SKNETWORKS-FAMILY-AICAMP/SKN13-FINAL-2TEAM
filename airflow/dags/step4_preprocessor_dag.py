# -*- coding: utf-8 -*-
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import os, re, pandas as pd

BASE = "./Complete"
BRAND_FILE = "./브랜드치환.py"

def load_brand_mapping():
    mapping = {}
    try:
        with open(BRAND_FILE, "r", encoding="utf-8") as f:
            code = compile(f.read(), BRAND_FILE, 'exec')
            loc = {}
            exec(code, {}, loc)
            if "BRAND_MAPPING" in loc:
                mapping = loc["BRAND_MAPPING"]
    except Exception as e:
        print(f"[WARN] 브랜드 매핑 로드 실패: {e}")
    return mapping

def step4_callable(date_folder: str, **_):
    in_dir = os.path.join(BASE, date_folder)
    infile = os.path.join(in_dir, "product_info_generalized.csv")
    outfile = os.path.join(in_dir, "product_info_step4.csv")

    df = pd.read_csv(infile, dtype=str).fillna("")
    brand_map = load_brand_mapping()

    out = pd.DataFrame({
        "사이트명": "29cm",
        "상품코드": df["제품번호"],
        "상품명": df["제품이름"],
        "한글브랜드명": df["브랜드"],
        "대분류": df["제품대분류"],
        "소분류": df["제품소분류"],
        "원가": df["원가"],
        "할인가": df["할인가"],
        "성별": df["성별"],
        "이미지URL": df["사진"],
        "소재": df["제품소재"],
        "색상": df["색상"],
        "좋아요수": "정보없음",
        "상품링크": "https://www.29cm.co.kr/products/" + df["제품번호"].astype(str),
        "영어브랜드명": df["브랜드"].map(brand_map).fillna(""),
    })

    out.to_csv(outfile, index=False, encoding="utf-8-sig")
    print(f"[Step4] Saved → {outfile}")

default_args = {
    "owner": "tjddml",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="step4_preprocessor",
    default_args=default_args,
    description="Step4: schema mapping + english brand",
    schedule_interval=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["29cm","preprocess","step4"],
) as dag:

    date_folder = "{{ ds | replace('-', '_') }}"

    t4 = PythonOperator(
        task_id="step4_run",
        python_callable=step4_callable,
        op_kwargs={"date_folder": date_folder},
    )

    trigger_step5 = TriggerDagRunOperator(
        task_id="trigger_step5",
        trigger_dag_id="step5_preprocessor",
        conf={"date_folder": date_folder},
        wait_for_completion=False,
    )

    t4 >> trigger_step5
