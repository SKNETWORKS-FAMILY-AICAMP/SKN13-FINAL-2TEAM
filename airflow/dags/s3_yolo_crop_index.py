from __future__ import annotations
from datetime import datetime, timedelta
import os, io, tempfile, shutil, logging
import pandas as pd
import requests
import boto3
from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from ultralytics import YOLO
from PIL import Image
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

# === 로거 ===
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# === Variables ===
AWS_ACCESS_KEY_ID     = Variable.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = Variable.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION            = Variable.get("AWS_REGION", default_var="ap-northeast-2")
S3_BUCKET             = Variable.get("S3_BUCKET_NAME")

CSV_KEY        = Variable.get("S3_CSV_KEY",   default_var="29cm_1000.csv")
MODEL_KEY      = Variable.get("S3_MODEL_KEY", default_var="best.pt")
# 플레이스홀더 지원: {대분류}, {label}, {category}
OUTPUT_PREFIX  = Variable.get("S3_OUTPUT_PREFIX", default_var="crop_image/")
ROW_LIMIT      = int(Variable.get("ROW_LIMIT", default_var="0"))

CONF_TH = float(Variable.get("YOLO_CONF", default_var="0.5"))
IOU_TH  = float(Variable.get("YOLO_IOU",  default_var="0.45"))

LABEL_MAP = {
    "상의": "top",
    "바지": "pants",
    "원피스": "dress",
    "스커트": "skirt",
}

default_args = {"owner": "airflow", "retries": 1, "retry_delay": timedelta(minutes=3)}

def s3_client():
    session = boto3.session.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    return session.client("s3")

def resolve_prefix(category_kr: str, target_label: str) -> str:
    """S3_OUTPUT_PREFIX에서 플레이스홀더를 실제 값으로 치환하고 끝에 / 보장"""
    p = OUTPUT_PREFIX
    p = p.replace("{대분류}", category_kr)
    p = p.replace("{category}", category_kr)
    p = p.replace("{label}", target_label)
    if p and not p.endswith("/"):
        p += "/"
    return p

def _clear_prefix_once(s3, bucket: str, prefix: str):
    """기존 이미지 정리: 업로드가 '처음으로 성공하기 직전' 1회만 호출"""
    paginator = s3.get_paginator("list_objects_v2")
    to_delete = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            to_delete.append({"Key": obj["Key"]})
    if not to_delete:
        logger.info("[CLEANUP] No existing objects under s3://%s/%s", bucket, prefix)
        return
    for i in range(0, len(to_delete), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": to_delete[i:i+1000]})
    logger.info("[CLEANUP] Deleted %d objects from s3://%s/%s", len(to_delete), bucket, prefix)

with DAG(
    dag_id="s3_yolo_crop_index",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    default_args=default_args,
    tags=["s3", "yolo", "crop"],
) as dag:

    @task()
    def download_model_from_s3() -> str:
        s3 = s3_client()
        tmpdir = tempfile.mkdtemp(prefix="yolo_model_")
        model_path = os.path.join(tmpdir, "best.pt")
        s3.download_file(S3_BUCKET, MODEL_KEY, model_path)
        logger.info("[MODEL] downloaded from s3://%s/%s → %s", S3_BUCKET, MODEL_KEY, model_path)
        return model_path

    @task()
    def process_and_upload_crops(model_path: str) -> int:
        model = YOLO(model_path)
        model.to("cpu")
        s3 = s3_client()

        # ✅ processed_data/ 안에서 최신 CSV 찾기
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="processed_data/")
        if "Contents" not in resp:
            raise FileNotFoundError("No files found in s3://%s/processed_data/" % S3_BUCKET)

        csv_files = [obj for obj in resp["Contents"] if obj["Key"].endswith(".csv")]
        if not csv_files:
            raise FileNotFoundError("No CSV files in processed_data/")

        latest_csv = max(csv_files, key=lambda x: x["LastModified"])["Key"]
        logger.info("[CSV] latest file selected: s3://%s/%s", S3_BUCKET, latest_csv)

        # ✅ 최신 CSV 읽기
        obj = s3.get_object(Bucket=S3_BUCKET, Key=latest_csv)
        df = pd.read_csv(io.BytesIO(obj["Body"].read()))

        if ROW_LIMIT > 0:
            df = df.head(ROW_LIMIT)

        total = len(df)
        logger.info("[CSV] loaded %d rows from %s", total, latest_csv)

        saved = 0
        cleared = False  # ✅ 첫 업로드 직전에 기존 프리픽스 삭제
        workdir = tempfile.mkdtemp(prefix="yolo_work_")
        try:
            for i, (_, row) in enumerate(df.iterrows(), start=1):
                product_id  = str(row["상품코드"])
                category_kr = str(row["대분류"]).strip()
                url         = str(row["이미지URL"]).strip()

                logger.info("[PROGRESS] %d/%d processing product_id=%s category=%s",
                            i, total, product_id, category_kr)

                target = LABEL_MAP.get(category_kr)
                if not target:
                    logger.warning("[SKIP] Unsupported category=%s (product_id=%s)", category_kr, product_id)
                    continue

                # 이미지 다운로드
                try:
                    r = requests.get(url, timeout=12)
                    r.raise_for_status()
                    img = Image.open(io.BytesIO(r.content)).convert("RGB")
                    logger.info("[DL] OK product_id=%s url=%s", product_id, url[:80])
                except Exception as e:
                    logger.error("[SKIP] Download fail product_id=%s url=%s err=%s", product_id, url[:80], e)
                    continue

                # YOLO 추론
                results = model(img, conf=CONF_TH, iou=IOU_TH, verbose=False)
                best = None
                for res in results:
                    if res.boxes is None:
                        continue
                    for box, cls, conf in zip(res.boxes.xyxy, res.boxes.cls, res.boxes.conf):
                        label = model.names[int(cls)].lower()
                        c = float(conf)
                        if label == target and c >= CONF_TH:
                            if (best is None) or (c > best[0]):
                                best = (c, box)

                if best is None:
                    logger.warning("[SKIP] product_id=%s target=%s → no detection >= %.2f",
                                product_id, target, CONF_TH)
                    continue

                # 크롭
                _, best_box = best
                x1, y1, x2, y2 = map(int, best_box.tolist())
                cropped = img.crop((x1, y1, x2, y2))

                # 저장 + 업로드
                fname = f"crop_{category_kr}_{product_id}.jpg"
                local = os.path.join(workdir, fname)
                cropped.save(local, format="JPEG", quality=95)

                prefix = resolve_prefix(category_kr, target)
                key = f"{prefix}{fname}"

                # ✅ 첫 성공 업로드 직전 기존 프리픽스 비우기
                if not cleared:
                    _clear_prefix_once(s3, bucket=S3_BUCKET, prefix=OUTPUT_PREFIX)
                    cleared = True

                s3.upload_file(local, S3_BUCKET, key, ExtraArgs={"ContentType": "image/jpeg"})
                saved += 1
                logger.info("[SAVED] %s (conf=%.2f) | progress %d/%d | saved=%d",
                            f"s3://{S3_BUCKET}/{key}", best[0], i, total, saved)

            logger.info("[DONE] total saved=%d of %d", saved, total)
            return saved, latest_csv
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


    @task()
    def report(result: tuple[int, str]):
        n, latest_csv = result
        logger.info("[REPORT] Uploaded crop images: %d (csv=%s)", n, latest_csv)
        print(f"[DONE] 업로드된 크롭 이미지 수: {n}, CSV={latest_csv}")
        return result  # 그대로 반환

    @task.short_circuit
    def has_crops(result: tuple[int, str]) -> bool:
        n, _ = result
        return (n or 0) > 0

    trigger_embedding = TriggerDagRunOperator(
        task_id="trigger_embedding",
        trigger_dag_id="embedding_pipeline",
        conf={
            "bucket": S3_BUCKET,
            "output_prefix": OUTPUT_PREFIX,
            "csv_key": "{{ ti.xcom_pull(task_ids='process_and_upload_crops')[1] }}"
        },
        wait_for_completion=False,
        reset_dag_run=True,
    )

    model_file = download_model_from_s3()
    result = process_and_upload_crops(model_file)
    r = report(result)
    c = has_crops(result)

    model_file >> result >> r
    c >> trigger_embedding