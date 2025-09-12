# -*- coding: utf-8 -*-
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import os

BASE = "./Complete"

def finalize_callable(date_folder: str = None, **context):
    # step5/6에서 넘긴 conf 우선 사용
    date_folder = (context.get("dag_run").conf.get("date_folder")
                   if context.get("dag_run") and context["dag_run"].conf.get("date_folder")
                   else date_folder)

    in_dir = os.path.join(BASE, date_folder)
    step4 = os.path.join(in_dir, "product_info_step4.csv")
    step5 = os.path.join(in_dir, "product_info_step5.csv")
    step6 = os.path.join(in_dir, "product_info_step6.csv")
    target = os.path.join(in_dir, "29cm_preprocessing_product_info.csv")

    if not os.path.exists(step6):
        raise FileNotFoundError(f"[Step7] Not found: {step6}")

    # 기존 타깃 파일 있으면 덮어쓰기
    if os.path.exists(target):
        os.remove(target)

    # 최종본 이름 변경 (step6 → 타깃명)
    os.rename(step6, target)
    print(f"[Step7] Renamed: {step6} → {target}")

    # 중간 산출물 삭제
    for p in [step4, step5]:
        if os.path.exists(p):
            os.remove(p)
            print(f"[Step7] Deleted: {p}")

default_args = {
    "owner": "tjddml",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="step7_finalize_preprocessing",
    default_args=default_args,
    description="Step7: rename final CSV and cleanup intermediates",
    schedule_interval=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["29cm", "preprocess", "step7"],
) as dag:

    date_folder_template = "{{ ds | replace('-', '_') }}"

    t7 = PythonOperator(
        task_id="finalize_and_cleanup",
        python_callable=finalize_callable,
        op_kwargs={"date_folder": date_folder_template},
        provide_context=True,
    )

    # 다음 DAG 트리거 (무신사 데이터 전처리)
    trigger_musinsa = TriggerDagRunOperator(
        task_id="trigger_musinsa_data_processing",
        trigger_dag_id="musinsa_data_processing",
        wait_for_completion=True,
        conf={"triggered_by": "step7_finalize_preprocessing"},
    )

    # 다음 DAG 트리거 (W컨셉 전처리 CSV)
    trigger_wconcept_preprocessor = TriggerDagRunOperator(
        task_id="trigger_wconcept_preprocessor_csv",
        trigger_dag_id="wconcept_preprocessor_csv",
        wait_for_completion=False,
        conf={"triggered_by": "musinsa_data_processing"},
    )
    
    # 실행 순서: Step7 → Musinsa Preprocessor(완료 대기) → Wconcept Preprocessor CSV
    t7 >> trigger_musinsa >> trigger_wconcept_preprocessor

