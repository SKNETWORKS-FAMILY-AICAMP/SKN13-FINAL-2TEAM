# -*- coding: utf-8 -*-
"""
step2_detail_api_fetcher_dag.py
"""
import os, re, json, time, random, logging
from datetime import datetime
import pandas as pd, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

BASE_DATA_PATH = "./29cm_data"
LINKS_BASE_PATH = os.path.join(BASE_DATA_PATH, "links")
JSON_BASE_PATH  = os.path.join(BASE_DATA_PATH, "json")
HTML_BASE_PATH  = os.path.join(BASE_DATA_PATH, "html")

# ✅ 폴더 보장 (Broken DAG 예방)
os.makedirs(LINKS_BASE_PATH, exist_ok=True)
os.makedirs(JSON_BASE_PATH,  exist_ok=True)
os.makedirs(HTML_BASE_PATH,  exist_ok=True)

DETAIL_API_TEMPLATE = "https://bff-api.29cm.co.kr/api/v5/product-detail/{item_id}"
DETAIL_API_METHOD   = "GET"

def build_detail_payload(item_id: str) -> dict:
    return {"itemId": item_id}

COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "origin": "https://www.29cm.co.kr",
    "referer": "https://www.29cm.co.kr/",
    "accept-language": "ko-KR,ko;q=0.9",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"),
}
WRITE_HTML_WRAPPER = False

def make_session():
    s = requests.Session()
    retries = Retry(total=4, backoff_factor=0.6,
                    status_forcelist=[429,500,502,503,504],
                    allowed_methods=["GET","POST"], raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://",  HTTPAdapter(max_retries=retries))
    return s

def fetch_detail_json(session: requests.Session, item_id: str, referer: str) -> dict:
    headers = COMMON_HEADERS.copy()
    headers["referer"] = referer or headers.get("referer","https://shop.29cm.co.kr/")
    url = DETAIL_API_TEMPLATE.format(item_id=item_id)
    resp = (session.get(url, headers=headers, timeout=20)
            if DETAIL_API_METHOD.upper()=="GET"
            else session.post(url, headers=headers, json=build_detail_payload(item_id), timeout=20))
    if resp.status_code >= 400:
        raise RuntimeError(f"API {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except Exception:
        m = re.search(r"\{.*\}", resp.text.strip(), re.S)
        if not m: raise
        return json.loads(m.group(0))

def write_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def write_initial_state_wrapper_html(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    html = f"""<!doctype html><html><head><meta charset="utf-8"></head>
<body><script>window.__INITIAL_STATE__ = {json.dumps(data, ensure_ascii=False)};</script></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

def task_fetch_detail_api_for_category(category_name: str, **kwargs):
    links_csv = os.path.join(LINKS_BASE_PATH, category_name, "links.csv")
    if not os.path.exists(links_csv):
        print(f"[{category_name}] links.csv 미존재: {links_csv}")
        return
    df = pd.read_csv(links_csv)
    if "id" not in df.columns or "link" not in df.columns:
        raise ValueError(f"[{category_name}] links.csv는 id, link 컬럼이 필요합니다.")
    s = make_session()
    saved = skipped = failed = 0
    for i, row in df.iterrows():
        item_id = str(row["id"]); link = str(row["link"])
        json_path = os.path.join(JSON_BASE_PATH, category_name, f"{item_id}.json")
        html_path = os.path.join(HTML_BASE_PATH, category_name, f"{item_id}.html")
        if os.path.exists(json_path):
            skipped += 1; print(f" - [{i+1}/{len(df)}] {item_id} skip"); continue
        time.sleep(random.uniform(0.5, 1.4))
        try:
            data = fetch_detail_json(s, item_id=item_id, referer=link)
            if not isinstance(data, dict): raise ValueError("응답이 dict JSON이 아님")
            write_json(json_path, data)
            if WRITE_HTML_WRAPPER: write_initial_state_wrapper_html(html_path, data)
            saved += 1; print(f" ✓ [{i+1}/{len(df)}] {item_id} 저장 완료")
        except Exception as e:
            failed += 1; logging.exception(f" ✗ [{i+1}/{len(df)}] {item_id} 실패: {e}")
    print(f"[{category_name}] 완료: 저장={saved}, 스킵={skipped}, 실패={failed}")

def task_fetch_all_categories(**kwargs):
    cats = [d for d in os.listdir(LINKS_BASE_PATH) if os.path.isdir(os.path.join(LINKS_BASE_PATH, d))]
    if not cats:
        print(f"links 폴더 비어있음: {LINKS_BASE_PATH}")
        return
    for cat in cats:
        # 기존 per-category 함수 재사용 (그대로 호출)
        task_fetch_detail_api_for_category(category_name=cat)

with DAG(
    dag_id="step2_detail_api_fetcher",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None, catchup=False, tags=["2_detail_api","29cm","bff"],
) as dag:
    start = PythonOperator(task_id="start", python_callable=lambda: print("step2 start"))
    fetch_all = PythonOperator(task_id="fetch_all_details", python_callable=task_fetch_all_categories)
    start >> fetch_all

    # 다음 DAG 트리거: 기다리지 않고 바로 넘김
    trigger_reviews = TriggerDagRunOperator(
        task_id="trigger_step2_reviews_api_fetcher",
        trigger_dag_id="step2_reviews_api_fetcher",
        wait_for_completion=False,
        conf={"triggered_by": "step2_detail_api_fetcher"},
    )
    fetch_all >> trigger_reviews
