# -*- coding: utf-8 -*-
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator   # ✅ 추가
from datetime import datetime, timedelta
import os, pandas as pd

BASE = "./Complete"

def step6_callable(date_folder: str = None, **context):
    date_folder = (context.get("dag_run").conf.get("date_folder")
                   if context.get("dag_run") and context["dag_run"].conf.get("date_folder")
                   else date_folder)

    in_dir = os.path.join(BASE, date_folder)
    infile = os.path.join(in_dir, "product_info_step5.csv")
    outfile = os.path.join(in_dir, "product_info_step6.csv")

    df = pd.read_csv(infile, dtype=str).fillna("")

    # 가격 숫자화
    for col in ["원가", "할인가"]:
        df[col] = df[col].str.replace(r"[^0-9]", "", regex=True)
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # 가격 일관성
    df = df.loc[df["할인가"] <= df["원가"]]

    # 필수 컬럼 결측 제거
    required = ["사이트명","상품코드","상품명","대분류","소분류","성별","이미지URL"]
    for c in required:
        df = df.loc[df[c].notna() & (df[c] != "")]

    # 상품링크 유효성
    df = df.loc[df["상품링크"].str.contains("https://www.29cm.co.kr/products/", na=False)]

    # 상품코드 중복 제거
    df = df.drop_duplicates(subset=["상품코드"], keep="first")

    df.to_csv(outfile, index=False, encoding="utf-8-sig")
    print(f"[Step6] Saved → {outfile}")

default_args = {
    "owner": "tjddml",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="step6_preprocessor",
    default_args=default_args,
    description="Step6: validation & final output",
    schedule_interval=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["29cm","preprocess","step6"],
) as dag:

    date_folder_template = "{{ ds | replace('-', '_') }}"

    t6 = PythonOperator(
        task_id="step6_run",
        python_callable=step6_callable,
        op_kwargs={"date_folder": date_folder_template},
        provide_context=True,
    )

    # ✅ Step7 자동 트리거
    trigger_step7 = TriggerDagRunOperator(
        task_id="trigger_step7",
        trigger_dag_id="step7_finalize_preprocessing",
        conf={"date_folder": date_folder_template},
        wait_for_completion=False,
    )

    t6 >> trigger_step7
