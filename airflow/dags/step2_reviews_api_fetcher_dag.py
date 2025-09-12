# -*- coding: utf-8 -*-
"""
step2_reviews_api_fetcher_dag.py
"""
import os, time, random, logging
from datetime import datetime
import pandas as pd, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


BASE = "./29cm_data"
LINKS_DIR   = os.path.join(BASE, "links")
REVIEWS_DIR = os.path.join(BASE, "reviews")

# ✅ 폴더 보장 (Broken DAG 예방)
os.makedirs(LINKS_DIR,   exist_ok=True)
os.makedirs(REVIEWS_DIR, exist_ok=True)

REVIEW_API_TMPL = "https://review-api.29cm.co.kr/api/v4/reviews?itemId={item_id}&page={page}&size={size}"
HEADERS = {
    "accept":"application/json, text/plain, */*",
    "origin":"https://www.29cm.co.kr",
    "referer":"https://www.29cm.co.kr/",
    "accept-language":"ko-KR,ko;q=0.9",
    "user-agent":("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
}

def make_session():
    s = requests.Session()
    retries = Retry(total=4, backoff_factor=0.7,
                    status_forcelist=[429,500,502,503,504],
                    allowed_methods=["GET","POST"], raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://",  HTTPAdapter(max_retries=retries))
    return s

def _extract_reviews(payload):
    if not payload: return [], True
    if isinstance(payload, dict):
        if isinstance(payload.get("list"), list):
            reviews = payload["list"]
            last = payload.get("last"); tp = payload.get("totalPages"); pg = payload.get("page")
            is_last = bool(last) if last is not None else ((pg+1)>=tp if (pg is not None and tp is not None) else len(reviews)==0)
            return reviews, is_last
        if isinstance(payload.get("content"), list):
            reviews = payload["content"]
            return reviews, bool(payload.get("last", len(reviews)==0))
        if "data" in payload: return _extract_reviews(payload["data"])
    if isinstance(payload, list): return payload, (len(payload)==0)
    return [], True

def fetch_reviews_for_item(session, item_id: str, referer: str, out_dir: str, page_size=40, max_pages=200):
    os.makedirs(out_dir, exist_ok=True)
    saved = 0
    for page in range(max_pages):
        url = REVIEW_API_TMPL.format(item_id=item_id, page=page, size=page_size)
        headers = HEADERS.copy(); headers["referer"] = referer or headers["referer"]
        r = session.get(url, headers=headers, timeout=20)
        if r.status_code == 404:
            logging.info(f"[{item_id}] 리뷰 엔드포인트 404"); break
        if r.status_code >= 400:
            logging.warning(f"[{item_id}] p{page} HTTP {r.status_code}: {r.text[:200]}")
        try:
            payload = r.json()
        except Exception:
            logging.warning(f"[{item_id}] p{page} JSON 파싱 실패"); break
        reviews, is_last = _extract_reviews(payload)
        if not reviews:
            if page == 0: logging.info(f"[{item_id}] 리뷰 없음")
            break
        out_path = os.path.join(out_dir, f"{item_id}__p{page}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            import json; json.dump(payload, f, ensure_ascii=False, indent=2)
        saved += 1
        time.sleep(random.uniform(0.4, 1.0))
        if is_last: break
    return saved

def task_fetch_reviews(category_name: str, **kwargs):
    csv_path = os.path.join(LINKS_DIR, category_name, "links.csv")
    if not os.path.exists(csv_path):
        print(f"[{category_name}] links.csv 없음"); return
    df = pd.read_csv(csv_path)
    sess = make_session()
    total_saved = 0
    for _, row in df.iterrows():
        item_id = str(row["id"]); referer = str(row["link"])
        odir = os.path.join(REVIEWS_DIR, category_name)
        cnt = fetch_reviews_for_item(sess, item_id, referer, odir)
        total_saved += cnt; print(f" - {item_id}: {cnt} page(s) saved")
    print(f"[{category_name}] done. pages saved = {total_saved}")

def task_fetch_reviews_all_categories(**kwargs):
    cats = [d for d in os.listdir(LINKS_DIR) if os.path.isdir(os.path.join(LINKS_DIR, d))]
    if not cats:
        print(f"links 폴더 비어있음: {LINKS_DIR}")
        return
    for cat in cats:
        task_fetch_reviews(category_name=cat)

with DAG(
    dag_id="step2_reviews_api_fetcher",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None, catchup=False, tags=["2_reviews_api","29cm"],
) as dag:
    start = PythonOperator(task_id="start", python_callable=lambda: print("reviews start"))
    fetch_all = PythonOperator(task_id="fetch_all_reviews", python_callable=task_fetch_reviews_all_categories)
    start >> fetch_all

    trigger_step3 = TriggerDagRunOperator(
        task_id="trigger_step3_preprocessor",
        trigger_dag_id="step3_preprocessor",
        wait_for_completion=False,
        conf={"triggered_by": "step2_reviews_api_fetcher"},
    )
    fetch_all >> trigger_step3
