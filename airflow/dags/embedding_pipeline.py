from __future__ import annotations
from datetime import datetime, timedelta
import os, io, tempfile, shutil, logging, importlib
import json 
import boto3
import pandas as pd
from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable

# --- Qdrant imports (version-safe) ---
from qdrant_client import QdrantClient

try:
    # >=1.7
    from qdrant_client.models import PointStruct, Distance, VectorParams
except Exception:
    # <=1.6 (fallback)
    from qdrant_client.http.models import PointStruct, Distance, VectorParams

# === 로거 ===
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# === Variables ===
AWS_ACCESS_KEY_ID     = Variable.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = Variable.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION            = Variable.get("AWS_REGION", default_var="ap-northeast-2")
S3_BUCKET             = Variable.get("S3_BUCKET_NAME")

# 크롭 이미지가 저장된 S3 prefix (예: "crop_image/")
CROP_PREFIX = Variable.get("S3_CROP_PREFIX", default_var="crop_image/")
# 최종 임베딩 CSV를 업로드할 S3 key (예: "embeddings/embedding_final.csv")
OUTPUT_KEY  = Variable.get("S3_EMBED_KEY",  default_var="embeddings/embedding_final.csv")
# 상품 정보 CSV (예: "29cm_1000.csv")
PRODUCT_CSV_KEY = Variable.get("S3_CSV_KEY", default_var="product_info.csv")

# Qdrant 연결 정보 
QDRANT_URL        = Variable.get("QDRANT_URL", default_var="http://43.201.185.192:6333")
QDRANT_COLLECTION = Variable.get("QDRANT_COLLECTION", default_var="ivlle")
QDRANT_API_KEY    = Variable.get("QDRANT_API_KEY", default_var="") 

# === 모듈 매핑 (대분류 → 파이썬 모듈 경로) ===
MODULE_MAP = {
    "상의":   "modules.top",
    "바지":   "modules.pants",
    "스커트": "modules.skirt",
    "원피스": "modules.dress",
}

default_args = {"owner": "airflow", "retries": 1, "retry_delay": timedelta(minutes=3)}

def s3_client():
    session = boto3.session.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    return session.client("s3")


with DAG(
    dag_id="embedding_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    default_args=default_args,
    tags=["s3", "embedding"],
) as dag:

    @task()
    def download_crop_images() -> str:
        """S3에서 CROP_PREFIX 이미지 전부 로컬 임시폴더로 다운로드."""
        s3 = s3_client()
        tmpdir = tempfile.mkdtemp(prefix="crop_dl_")
        paginator = s3.get_paginator("list_objects_v2")
        cnt = 0
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=CROP_PREFIX):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                local_path = os.path.join(tmpdir, os.path.basename(key))
                s3.download_file(S3_BUCKET, key, local_path)
                cnt += 1
        logger.info("[DOWNLOAD] %d crop images from s3://%s/%s → %s", cnt, S3_BUCKET, CROP_PREFIX, tmpdir)
        return tmpdir

    @task()
    def run_embeddings(crop_dir: str) -> str:
        """
        - 상품 CSV 내려받아 (상품코드→(대분류, 소분류)) 매핑 구성
        - 파일명 crop_{대분류}_{상품코드}.jpg 파싱
        - 모듈.process_one(image_path, product_id, category_kr, type_kr) 호출
        - CSV 저장
        """
        # OpenAI 키 환경변수로 주입
        os.environ["OPENAI_API_KEY"] = Variable.get("OPENAI_API_KEY")

        # --- S3에서 상품 CSV 다운로드 & 매핑 생성
        s3 = s3_client()
        obj = s3.get_object(Bucket=S3_BUCKET, Key=PRODUCT_CSV_KEY)
        df_info = pd.read_csv(io.BytesIO(obj["Body"].read()), dtype=str).fillna("")
        if not set(["상품코드", "대분류", "소분류"]).issubset(df_info.columns):
            raise RuntimeError("상품 CSV에 '상품코드','대분류','소분류' 컬럼이 필요합니다.")
        pid_map = dict(zip(df_info["상품코드"].astype(str), zip(df_info["대분류"].astype(str), df_info["소분류"].astype(str))))
        logger.info("[PRODUCT CSV] rows=%d key=s3://%s/%s", len(df_info), S3_BUCKET, PRODUCT_CSV_KEY)

        # --- 처리 대상 파일 수집
        exts = (".jpg", ".jpeg", ".png")
        file_list = [f for f in os.listdir(crop_dir) if f.lower().endswith(exts)]
        total = len(file_list)
        if total == 0:
            raise RuntimeError("No crop images found to embed")
        logger.info("[EMBED] start: files=%d, dir=%s", total, crop_dir)

        records = []
        for idx, fname in enumerate(file_list, start=1):
            try:
                _, category_kr, product_tail = fname.split("_", 2)
                product_id = os.path.splitext(product_tail)[0]
            except Exception:
                logger.warning("[SKIP] (%d/%d) unexpected filename=%s", idx, total, fname)
                continue

            module_name = MODULE_MAP.get(category_kr)
            if not module_name:
                logger.warning("[SKIP] (%d/%d) unknown category=%s file=%s", idx, total, category_kr, fname)
                continue

            # CSV에서 소분류(type_kr) 조회 (없으면 빈 문자열)
            major_kr, type_kr = pid_map.get(product_id, (category_kr, ""))
            image_path = os.path.join(crop_dir, fname)

            # ▶ 진행상황 로그 (기존 한 줄을 더 또렷하게)
            logger.info("[EMBED] %d/%d start id=%s (%s / %s)", idx, total, product_id, category_kr, (type_kr or "unknown"))
            try:
                module = importlib.import_module(module_name)
                rec = module.process_one(image_path, product_id, category_kr, type_kr)
                records.append(rec)
                # 완료 로그
                logger.info("[EMBED] %d/%d done id=%s", idx, total, product_id)                
            except Exception as e:
                logger.error("[FAIL] %d/%d id=%s (%s / %s) err=%s", idx, total, product_id, category_kr, type_kr, e)
            # 10개 단위로 중간 집계
            if idx % 10 == 0:
                logger.info("[EMBED] progress: processed=%d/%d saved=%d", idx, total, len(records))
        if not records:
            raise RuntimeError("No embedding results produced")

        df = pd.DataFrame(records)
        local_csv = os.path.join(crop_dir, "embedding_final.csv")
        df.to_csv(local_csv, index=False, encoding="utf-8")
        logger.info("[SAVE] local embedding CSV: %s rows=%d (saved=%d/%d)", local_csv, len(df), len(records), total)
        return local_csv

    @task()
    def upload_to_s3(local_csv: str):
        """최종 CSV를 S3에 업로드"""
        try:
            rows = pd.read_csv(local_csv, nrows=0)
            row_count = sum(1 for _ in open(local_csv, "rb")) - 1
        except Exception:
            row_count = -1 
        size_mb = os.path.getsize(local_csv) / (1024 * 1024)
        logger.info("[UPLOAD] source=%s size=%.2fMB rows~=%s", local_csv, size_mb, (row_count if row_count>=0 else "unknown"))

        s3 = s3_client()
        s3.upload_file(local_csv, S3_BUCKET, OUTPUT_KEY)
        logger.info("[UPLOAD] s3://%s/%s", S3_BUCKET, OUTPUT_KEY)
        print(f"✅ Embedding CSV uploaded: s3://{S3_BUCKET}/{OUTPUT_KEY} (≈{row_count} rows)")


    @task()
    def ingest_to_qdrant():
        """
        S3의 embedding_final.csv를 읽어 Qdrant(ivlle 등)에 upsert.
        CSV 컬럼: id, category, type, information, text(옵션), multi(옵션)
        - 기존 컬렉션은 유지(데이터 누적). 없으면 생성.
        """
        import json
        import pandas as pd
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct

        # ----- 환경/설정 -----
        s3 = s3_client()
        tmpdir = tempfile.mkdtemp(prefix="qdr_dl_")
        local_csv = os.path.join(tmpdir, "embedding_final.csv")
        
        # Airflow Variables (없으면 기본값)
        QDRANT_URL         = Variable.get("QDRANT_URL")
        QDRANT_API_KEY     = Variable.get("QDRANT_API_KEY", default_var="") or None
        QDRANT_COLLECTION  = Variable.get("QDRANT_COLLECTION", default_var="ivlle")
        QDRANT_BATCH       = int(Variable.get("QDRANT_BATCH", default_var="500"))

        # ----- S3에서 CSV 다운로드 -----
        s3.download_file(S3_BUCKET, OUTPUT_KEY, local_csv)
        df = pd.read_csv(local_csv, dtype=str).fillna("")
        if "id" not in df.columns or "information" not in df.columns:
            raise RuntimeError("CSV must contain at least 'id' and 'information' columns")

        has_multi = "multi" in df.columns and df["multi"].str.len().gt(2).any()
        has_text  = "text"  in df.columns and df["text"].str.len().gt(2).any()
        if not (has_multi or has_text):
            raise RuntimeError("CSV에 'multi' 또는 'text' 벡터 컬럼이 없습니다.")

        # ----- Qdrant Client -----
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60.0)

        # 컬렉션 존재 체크 → 없으면 생성(기존 데이터 보존)
        try:
            client.get_collection(QDRANT_COLLECTION)
            logger.info("[QDRANT] collection exists: %s", QDRANT_COLLECTION)
        except Exception:
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config={
                    "text":  VectorParams(size=512, distance=Distance.COSINE),
                    "multi": VectorParams(size=512, distance=Distance.COSINE),
                },
            )
            logger.info("[QDRANT] collection created: %s", QDRANT_COLLECTION)

        # ----- 배치 업서트 -----
        total = len(df)
        bsz = max(1, QDRANT_BATCH)
        logger.info("[QDRANT] upsert start: rows=%d, batch=%d, url=%s, col=%s",
                    total, bsz, QDRANT_URL, QDRANT_COLLECTION)


        done = 0
        for i in range(0, total, bsz):
            sl = df.iloc[i:i+bsz]
            points = []
            for _, row in sl.iterrows():
                rid = str(row["id"]).strip()
                try:
                    pid = int(rid)
                except Exception:
                    pid = rid  # string id 허용

                payload = {
                        "category": row.get("category", ""),
                        "type": row.get("type", ""),
                        "information": row.get("information", ""),
                    }

                vec = {}
                if has_text and row.get("text", ""):
                    vec["text"] = json.loads(row["text"])
                if has_multi and row.get("multi", ""):
                    vec["multi"] = json.loads(row["multi"])

                if not vec:
                    logger.error("[QDRANT] skip row(no vectors) id=%s", pid)
                    continue

                points.append(PointStruct(id=pid, payload=payload, vector=vec))

            if points:
                client.upsert(collection_name=QDRANT_COLLECTION, points=points)
                logger.info("[QDRANT] batch upserted: %d points (rows %d-%d)", len(points), i+1, i+len(sl))
            else: 
                logger.info("[QDRANT] batch skipped (no valid points) rows %d-%d", i+1, i+len(sl))
            done += len(sl)
            pct = (done/total*100.0) if total else 100.0
            logger.info("[QDRANT] progress: %d/%d (%.1f%%)", done, total, pct)
        shutil.rmtree(tmpdir, ignore_errors=True)
        logger.info("✅ Qdrant upsert complete: %d rows → %s", total, QDRANT_COLLECTION)


    # 의존성
    crop_dir = download_crop_images()
    local_csv = run_embeddings(crop_dir)
    uploaded = upload_to_s3(local_csv)
    ingested = ingest_to_qdrant()
    uploaded >> ingested
