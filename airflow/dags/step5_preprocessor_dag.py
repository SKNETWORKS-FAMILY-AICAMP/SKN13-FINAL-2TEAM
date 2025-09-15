# -*- coding: utf-8 -*-
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import os, re, pandas as pd

BASE = "./Complete"

# ---------- 유틸: 상품명 클리닝 ----------
def clean_product_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = re.sub(r"\[.*?\]|\(.*?\)", "", name)  # 대/소괄호 + 내용 제거
    if "_" in name:  # 색상/옵션 패턴 제거
        name = name.rsplit("_", 1)[0]
    return re.sub(r"\s+", " ", name).strip()

# ---------- 0) 대분류 표준화: 상의/바지/스커트/원피스 ----------
def infer_main_category(subcat: str, name: str) -> str:
    s = (subcat or "").lower()
    n = (name or "").lower()

    # 스커트
    if any(k in s for k in ["스커트", "skirt"]) or any(k in n for k in ["스커트", "skirt"]):
        return "스커트"
    # 원피스
    if any(k in s for k in ["원피스", "dress", "ops"]) or any(k in n for k in ["원피스", "dress", "ops"]):
        return "원피스"
    # 바지(하의)
    pants_kw = ["팬츠","pants","슬랙스","slacks","치노","chino","조거","jogger","숏","short",
                "반바지","데님","denim","진","jean","와이드","wide","스트레이트","straight",
                "카고","cargo","테이퍼드","tapered","부츠컷","bootcut","레깅스","leggings","타이츠","tights"]
    if any(k in s for k in pants_kw) or any(k in n for k in pants_kw):
        return "바지"
    # 상의
    top_kw = ["티셔츠","t-shirt","tee","셔츠","블라우스","니트","sweater","스웨트","sweat",
              "후드","hood","hoodie","피케","폴로","카라","cardigan","가디건","슬리브리스",
              "sleeveless","나시","탱크","tank","아노락","anorak","플리스","fleece",
              "바람막이","나일론","nylon","재킷","자켓","jacket"]
    if any(k in s for k in top_kw) or any(k in n for k in top_kw):
        return "상의"

    return ""  # 판단 불가

# ---------- 2) 소분류 정규화 ----------
def normalize_subcategory(row):
    main = row["대분류"]
    sub = (row["소분류"] or "").strip()
    low = sub.lower()
    name_low = (row["상품명"] or "").lower()

    # 공통: 사전 치환(반소매/긴소매 티셔츠 → 반소매/긴소매)
    if sub in ["반소매 티셔츠", "반소매티셔츠", "short sleeve t-shirt", "short sleeve tee"]:
        return "반소매"
    if sub in ["긴소매 티셔츠", "긴소매티셔츠", "long sleeve t-shirt", "long sleeve tee"]:
        return "긴소매"

    if main == "상의":
        # 직접 매핑
        direct_map = {
            "후디":"후드티","후드 집업":"후드티","후드":"후드티",
            "긴소매 셔츠":"셔츠블라우스","반소매 셔츠":"셔츠블라우스","셔츠":"셔츠블라우스","블라우스":"셔츠블라우스","셔츠/블라우스":"셔츠블라우스",
            "긴소매 티셔츠":"긴소매","반소매 티셔츠":"반소매","티셔츠":"반소매",
            "피케/카라 티셔츠":"피케카라","폴로 셔츠":"피케카라","폴로셔츠":"피케카라",
            "스웨트셔츠":"니트스웨터","크루넥":"니트스웨터","카디건":"니트스웨터","니트웨어":"니트스웨터","터틀넥":"니트스웨터","브이넥":"니트스웨터","기타 니트":"니트스웨터",
            "슬리브리스":"슬리브리스","브라탑/캐미솔":"슬리브리스",
            "아노락":"애슬레저","트레이닝 재킷":"애슬레저","트레이닝 팬츠":"애슬레저","트레이닝":"애슬레저",
            "스웻/트레이닝 셋업":"애슬레저","바람막이":"애슬레저","나일론 재킷":"애슬레저","나일론/코치 재킷":"애슬레저",
            "플리스":"애슬레저","커버업":"애슬레저","비치 스윔웨어":"애슬레저","비키니":"애슬레저",
            "데님 자켓":"애슬레저","데님 재킷":"애슬레저","재킷":"애슬레저","자켓":"애슬레저"
        }
        if sub in direct_map:
            return direct_map[sub]

        # 키워드
        if any(k in low for k in ["후드","hood"]): return "후드티"
        if any(k in low for k in ["셔츠","shirt","블라우스","blouse"]): return "셔츠블라우스"
        if any(k in low for k in ["긴소매","long sleeve","l/s"]): return "긴소매"
        if any(k in low for k in ["반소매","short sleeve","s/s","티셔츠","tee","t-shirt"]): return "반소매"
        if any(k in low for k in ["피케","pike","카라","collar","폴로","polo"]): return "피케카라"
        if any(k in low for k in ["스웨트","sweat","크루넥","crew","카디건","cardigan","니트","knit","터틀넥","turtle","브이넥","v-neck"]): return "니트스웨터"
        if any(k in low for k in ["슬리브리스","sleeveless","나시","탱크","tank","브라탑","캐미솔","camisole","bra"]): return "슬리브리스"
        if any(k in low for k in ["트레이닝","training","아노락","anorak","스포츠","sport","바람막이","나일론","nylon","플리스","fleece","스윔","swim","비치","beach","비키니","bikini","커버업","cover","재킷","자켓","jacket"]): 
            return "애슬레저"
        return ""

    if main == "바지":
        # 우선 규칙: 카고
        if ("카고" in name_low) or ("chargo" in name_low) or ("cargo" in name_low):
            return "카고팬츠"

        # 직접 매핑
        direct_map = {
            "데님 팬츠":"데님팬츠","데님":"데님팬츠",
            "트레이닝 팬츠":"트레이닝조거팬츠","트레이닝":"트레이닝조거팬츠","스웻/트레이닝 셋업":"트레이닝조거팬츠",
            "기타 팬츠":"코튼팬츠","와이드 팬츠":"코튼팬츠","스트레이트 팬츠":"코튼팬츠","와이드":"코튼팬츠","스트레이트":"코튼팬츠",
            "코튼 팬츠":"코튼팬츠","슬림 팬츠":"코튼팬츠","슬림":"코튼팬츠","부츠컷":"코튼팬츠","팬츠":"코튼팬츠",
            "슬랙스":"슈트팬츠슬랙스","수트 셋업":"슈트팬츠슬랙스","수트/정장 셋업":"슈트팬츠슬랙스","블레이저":"슈트팬츠슬랙스",
            "쇼트":"숏팬츠","숏 팬츠":"숏팬츠","남성 스윔웨어":"숏팬츠","비치 스윔웨어":"숏팬츠","비키니":"숏팬츠"
        }
        if sub in direct_map:
            return direct_map[sub]

        # 키워드
        if any(k in low for k in ["데님","denim","진","jean"]): return "데님팬츠"
        if any(k in low for k in ["트레이닝","training","조거","jogger","스웨트","sweat","스웻","sweatpants","조깅","jogging"]): return "트레이닝조거팬츠"
        if any(k in low for k in ["슬랙스","slacks","수트","suit","정장","블레이저","blazer","드레스","dress","포멀","formal"]): return "슈트팬츠슬랙스"
        if any(k in low for k in ["쇼트","short","숏","반바지","스윔","swim","비치","beach"]): return "숏팬츠"
        if any(k in low for k in ["레깅스","leggings","타이츠","tights"]): return "레깅스"  # 이후 제거 규칙 적용
        if any(k in low for k in ["팬츠","pants","와이드","wide","스트레이트","straight","슬림","slim","코튼","cotton","치노","chino","카고","cargo","부츠컷","bootcut","테이퍼드","tapered","플레어","flare"]): 
            return "코튼팬츠"
        return ""

    if main == "스커트":
        # 직접
        if sub in ["미니","미니 스커트","mini","숏","short","쇼트"]: return "미니스커트"
        if sub in ["롱","롱 스커트","long","맥시","maxi"]: return "롱스커트"
        if sub in ["미디","미디 스커트","midi","미드","mid"]: return "미디스커트"
        # 키워드 + 상품명 보조
        if any(k in low for k in ["mini","미니","short","숏","쇼트"]) or any(k in name_low for k in ["mini","미니","short","숏"]): 
            return "미니스커트"
        if any(k in low for k in ["long","롱","maxi","맥시"]) or any(k in name_low for k in ["long","롱","maxi","맥시"]): 
            return "롱스커트"
        if any(k in low for k in ["midi","미디","mid"]) or any(k in name_low for k in ["midi","미디","mid"]): 
            return "미디스커트"
        return ""

    if main == "원피스":
        if sub in ["미니 원피스","미니","mini","숏","short"]: return "미니원피스"
        if sub in ["롱 원피스","롱","long","맥시","maxi"]: return "맥시원피스"
        if sub in ["미디 원피스","미디","midi","미드","mid"]: return "미디원피스"
        if any(k in low for k in ["mini","미니","short","숏"]) or any(k in name_low for k in ["mini","미니","short","숏"]): 
            return "미니원피스"
        if any(k in low for k in ["long","롱","maxi","맥시"]) or any(k in name_low for k in ["long","롱","maxi","맥시"]): 
            return "맥시원피스"
        if any(k in low for k in ["midi","미디","mid"]) or any(k in name_low for k in ["midi","미디","mid"]): 
            return "미디원피스"
        return ""

    return ""  # 해당 없으면 미매칭 처리

# ---------- 메인 작업 ----------
def step5_callable(date_folder: str = None, **context):
    date_folder = (context.get("dag_run").conf.get("date_folder")
                   if context.get("dag_run") and context["dag_run"].conf.get("date_folder")
                   else date_folder)

    in_dir = os.path.join(BASE, date_folder)
    infile = os.path.join(in_dir, "product_info_step4.csv")
    outfile = os.path.join(in_dir, "product_info_step5.csv")

    df = pd.read_csv(infile, dtype=str).fillna("")

    # 1) 상품명 클리닝 먼저
    df["상품명"] = df["상품명"].apply(clean_product_name)

    # 2) 대분류 표준화
    #  - "하의"는 그대로 "바지"로 바꿈(지시사항)
    df.loc[df["대분류"] == "하의", "대분류"] = "바지"
    #  - "남성의류/여성의류" 등 비표준 대분류는 소분류/상품명으로 추론
    mask_unstd = df["대분류"].isin(["남성의류","여성의류","남성","여성","의류","패션의류","의류잡화","", None])
    df.loc[mask_unstd, "대분류"] = df.loc[mask_unstd].apply(
        lambda r: infer_main_category(r.get("소분류",""), r.get("상품명","")), axis=1
    )

    # 3) 소분류 정규화
    df["소분류"] = df.apply(normalize_subcategory, axis=1)

    # 4) 바지 규칙 후처리
    #  - 레깅스 제거
    leggings_mask = (df["대분류"] == "바지") & (df["소분류"].fillna("").str.contains("레깅스"))
    df = df.loc[~leggings_mask]

    #  - 표기 변경
    replace_map = {
        "트레이닝조거팬츠": "트레이닝/조거팬츠",
        "슈트팬츠슬랙스": "슈트팬츠/슬랙스",
        "셔츠블라우스": "셔츠/블라우스",
        "피케카라": "피케/카라",
        "니트스웨터": "니트/스웨터",
    }
    df["소분류"] = df["소분류"].replace(replace_map)

    # 5) 미매칭/기타/공란 삭제
    df = df.loc[df["대분류"].isin(["상의","바지","스커트","원피스"])]
    df = df.loc[~df["소분류"].isin(["기타", "", None])]

    # 6) 저장
    df.to_csv(outfile, index=False, encoding="utf-8-sig")
    print(f"[Step5] Saved → {outfile}")

# ---------- DAG ----------
default_args = {
    "owner": "tjddml",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="step5_preprocessor",
    default_args=default_args,
    description="Step5: main-category normalization + name cleaning + subcategory normalization/fixes",
    schedule_interval=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["29cm","preprocess","step5"],
) as dag:

    date_folder_template = "{{ ds | replace('-', '_') }}"

    t5 = PythonOperator(
        task_id="step5_run",
        python_callable=step5_callable,
        op_kwargs={"date_folder": date_folder_template},
        provide_context=True,
    )

    trigger_step6 = TriggerDagRunOperator(
        task_id="trigger_step6",
        trigger_dag_id="step6_preprocessor",
        conf={"date_folder": date_folder_template},
        wait_for_completion=False,
    )

    t5 >> trigger_step6
