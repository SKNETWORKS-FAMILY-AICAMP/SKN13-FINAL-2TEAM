import pandas as pd
import os
import requests
from datetime import datetime

from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


# 설정 영역
CATEGORIES_TO_CRAWL = [
    {'name': 'womens_top', 'largeId': 268100100, 'middleId': 268103100},
    {'name': 'womens_pants', 'largeId': 268100100, 'middleId': 268106100},
    {'name': 'womens_skirt', 'largeId': 268100100, 'middleId': 268107100},
    {'name': 'womens_onepiece', 'largeId': 268100100, 'middleId': 268104100},
    {'name': 'mens_top', 'largeId': 272100100, 'middleId': 272103100},
    {'name': 'mens_pants', 'largeId': 272100100, 'middleId': 272104100},
]
BASE_SAVE_PATH = "./29cm_data/links"

# Airflow Task 함수
def task_get_product_links_api(name, largeId, middleId, **kwargs):
    cat_name, large_id, middle_id = name, largeId, middleId
    
    # ★★★ 수정 포인트: 날짜 없는 단순한 폴더 경로 사용 ★★★
    links_dir_path = os.path.join(BASE_SAVE_PATH, cat_name)
    os.makedirs(links_dir_path, exist_ok=True)
    csv_file_path = os.path.join(links_dir_path, "links.csv")

    api_url = "https://display-bff-api.29cm.co.kr/api/v1/listing/items"
    payload = {
        "pageType": "CATEGORY_PLP", "sortType": "NEWEST",
        "facets": {"categoryFacetInputs": [{"largeId": large_id, "middleId": middle_id}], "sortFacetInput": {"type": "NEWEST", "order": "DESC"}},
        "pageRequest": {"page": 1, "size": 50}
    }
    headers = {
        'accept': '*/*', 'content-type': 'application/json', 'origin': 'https://shop.29cm.co.kr',
        'referer': 'https://shop.29cm.co.kr/', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    
    response = requests.post(api_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    product_list = data.get('data', {}).get('list', [])
    if not product_list: raise ValueError(f"[{cat_name}] API 응답에서 상품 목록을 찾을 수 없습니다.")

    results = [{'id': item.get('itemId'), 'link': item.get('itemUrl', {}).get('webLink')}
               for item in product_list if item.get('itemId') and item.get('itemUrl', {}).get('webLink')]
    
    df = pd.DataFrame(results)
    df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
    print(f"★★★★★ [성공][{cat_name}] 총 {len(results)}개 링크를 '{csv_file_path}'에 저장했습니다. ★★★★★")
    
# Airflow DAG 정의
with DAG(
    dag_id='step1_link_collector',
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=['1_link_collection', 'api', '29cm'],
) as dag:
    start_task = PythonOperator(
        task_id='start_task',
        python_callable=lambda: print("Link collection DAG started")
    )

    collect_tasks = []  # ← 추가
    for category in CATEGORIES_TO_CRAWL:
        collect_task = PythonOperator(
            task_id=f'collect_links_{category["name"]}',
            python_callable=task_get_product_links_api,
            op_kwargs=category
        )
        start_task >> collect_task
        collect_tasks.append(collect_task)  # ← 추가

    # 모든 카테고리 수집 완료 대기(조인)
    join_after_collect = EmptyOperator(task_id="join_after_collect")  # ← 추가
    for t in collect_tasks:
        t >> join_after_collect

    # 다음 DAG 트리거 (상세 API 수집)
    trigger_step2 = TriggerDagRunOperator(                      # ← 추가
        task_id="trigger_step2_detail_api_fetcher",
        trigger_dag_id="step2_detail_api_fetcher",
        wait_for_completion=False,
        conf={"triggered_by": "step1_link_collector"},
    )
    join_after_collect >> trigger_step2