import os
import tempfile
import logging
import boto3
from PIL import Image
import io
import importlib
import base64
import json
import torch
from ultralytics.nn.tasks import DetectionModel
from ultralytics import YOLO
from qdrant_client import QdrantClient
from openai import AsyncOpenAI

# === 로거, 클라이언트, 환경변수 설정 ===
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
MODEL_KEY = os.getenv("S3_MODEL_KEY", "best.pt")
QDRANT_URL = os.getenv("QDRANT_URL", "http://43.201.185.192:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ivlle")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)
GPT_MODEL = "gpt-4o-mini"
torch.serialization.add_safe_globals([DetectionModel])
# === 모델 및 클라이언트 초기화 (싱글톤) ===
yolo_model = None
qdrant_client = None

# === 카테고리 매핑 ===
EN_TO_KO_MAP = {'top': '상의', 'pants': '하의', 'dress': '원피스'}

# 각 모듈의 한글 소분류 리스트 (GPT 프롬프트용)
TOP_SUB_CATS_KO = ['후드티', '셔츠블라우스', '긴소매', '반소매', '피케카라', '니트스웨터', '슬리브리스']
PANTS_SUB_CATS_KO = ['데님팬츠', '트레이닝조거팬츠', '코튼팬츠', '슈트팬츠슬랙스', '슈트슬랙스', '숏팬츠', '레깅스', '카고팬츠']
DRESS_SUB_CATS_KO = ['미니원피스', '미디원피스', '맥시원피스']
MAJOR_TO_SUB_CAT_MAP_KO = {
    "top": TOP_SUB_CATS_KO,
    "pants": PANTS_SUB_CATS_KO,
    "dress": DRESS_SUB_CATS_KO,
}

def get_s3_client():
    return boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_REGION)

def get_yolo_model():
    global yolo_model
    if yolo_model is None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "best.pt")
            try:
                s3 = get_s3_client()
                s3.download_file(S3_BUCKET, MODEL_KEY, model_path)
                logger.info(f"YOLO 모델 다운로드 완료: s3://{S3_BUCKET}/{MODEL_KEY}")
                yolo_model = YOLO(model_path)
                yolo_model.to("cpu")
            except Exception as e:
                logger.error(f"YOLO 모델 로드 실패: {e}")
                raise
    return yolo_model

def get_qdrant_client():
    global qdrant_client
    if qdrant_client is None:
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60.0) if QDRANT_API_KEY else QdrantClient(url=QDRANT_URL, timeout=60.0)
    return qdrant_client


async def get_subcategory_from_gpt(image_bytes: bytes, major_category_en: str) -> str:
    """GPT를 사용하여 이미지와 대분류 정보로 한글 소분류를 추론합니다."""
    sub_cat_list_ko = MAJOR_TO_SUB_CAT_MAP_KO.get(major_category_en)
    if not sub_cat_list_ko:
        logger.warning(f"{major_category_en}에 해당하는 소분류 리스트가 없습니다.")
        return ""

    prompt = f"""\
    You are a fashion specialist AI. Analyze the user-uploaded image and determine the most appropriate minor category for the main clothing item, which is a '{major_category_en}'.
    Choose ONE from the following Korean list: {sub_cat_list_ko}
    Return only the single, most appropriate minor category name from the list, exactly as it appears in the list.
    Example response: "후드티"
    """
    
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = await aclient.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ],
                }
            ],
            max_tokens=50,
            temperature=0.0,
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"GPT 소분류 추론 결과: {result}")
        # 간단한 유효성 검사
        return result if result in sub_cat_list_ko else ""

    except Exception as e:
        logger.error(f"GPT 소분류 추론 실패: {e}")
        return ""


def crop_image_with_yolo(image_bytes: bytes, category: str) -> bytes | None:
    """YOLO 모델로 이미지에서 특정 카테고리의 객체를 찾아 크롭합니다."""
    logger.info(f"YOLO 객체 탐지 시작 (타겟: {category})")
    model = get_yolo_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    LABEL_MAP = {"top": "top", "pants": "pants", "dress": "dress"}
    target_label = LABEL_MAP.get(category)
    if not target_label:
        return None

    results = model(img, conf=0.5, iou=0.45, verbose=False)
    
    best_detection = None
    for res in results:
        if res.boxes is None: continue
        for box, cls, conf in zip(res.boxes.xyxy, res.boxes.cls, res.boxes.conf):
            if model.names[int(cls)].lower() == target_label:
                confidence = float(conf)
                if best_detection is None or confidence > best_detection[0]:
                    best_detection = (confidence, box)

    if best_detection is None:
        logger.warning(f"객체를 찾지 못했습니다 (타겟: {target_label}, 신뢰도 0.5 이상).")
        return None

    _, best_box = best_detection
    # PIL crop은 튜플을 기대하므로, map 객체를 튜플로 변환합니다.
    cropped_img = img.crop(tuple(map(int, best_box.tolist())))
    
    buffer = io.BytesIO()
    cropped_img.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


async def get_embeddings_for_cropped_image(cropped_bytes: bytes, category_en: str, category_ko: str, type_ko: str) -> dict:
    """크롭된 이미지와 텍스트 정보를 바탕으로 임베딩을 생성합니다."""
    logger.info(f"임베딩 생성 시작 (카테고리: {category_en}, 타입: {type_ko})")
    MODULE_MAP = {"top": "modules.top", "pants": "modules.pants", "dress": "modules.dress"}
    
    module_name = MODULE_MAP.get(category_en)
    if not module_name: raise ValueError(f"지원하지 않는 카테고리입니다: {category_en}")
        
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

    try:
        module = importlib.import_module(module_name)
        if not hasattr(module, "process_single_item"): raise RuntimeError(f"모듈 '{module_name}'에 process_single_item 함수가 필요합니다.")

        embedding_result = await module.process_single_item(cropped_bytes, "user_upload", category_ko, type_ko)
        logger.info("임베딩 생성 완료.")
        return embedding_result
        
    except Exception as e:
        logger.error(f"임베딩 생성 중 오류 발생: {e}")
        raise


def search_similar_items_in_qdrant(embeddings: dict, limit: int = 5) -> list:
    """Qdrant에서 유사한 아이템을 검색합니다."""
    logger.info("Qdrant 유사도 검색 시작...")
    client = get_qdrant_client()
    
    query_vector = embeddings.get("multi") or embeddings.get("text")
    if not query_vector: raise ValueError("유효한 쿼리 벡터가 없습니다.")

    search_result = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=("multi", query_vector),
        limit=limit,
        with_payload=True
    )
    
    logger.info(f"Qdrant 유사도 검색 완료. {len(search_result)}개 결과 수신.")
    
    return [{"id": point.id, "score": point.score, **point.payload} for point in search_result]

# === 메인 파이프라인 함수 ===

async def recommend_by_image(image_bytes: bytes, category_en: str, sub_category_ko: str) -> dict:
    """
    이미지 추천의 전체 파이프라인을 실행합니다.
    대분류, 소분류는 외부에서 분류된 값을 받습니다.
    """
    try:
        # 1. YOLO로 객체 탐지 및 크롭
        cropped_bytes = crop_image_with_yolo(image_bytes, category_en)
        if not cropped_bytes:
            return {"error": "이미지에서 의류를 찾지 못했습니다. 다른 이미지를 사용해 주세요."}

        # 2. 크롭된 이미지로 임베딩 생성
        category_ko = EN_TO_KO_MAP.get(category_en, "")
        embeddings = await get_embeddings_for_cropped_image(cropped_bytes, category_en, category_ko, sub_category_ko)
        if not embeddings:
             return {"error": "이미지 특징을 추출하는 데 실패했습니다."}

        # 3. Qdrant에서 유사 아이템 검색
        recommendations = search_similar_items_in_qdrant(embeddings)
        
        return {"recommendations": recommendations, "information": embeddings.get("information")}

    except Exception as e:
        logger.exception(f"이미지 추천 파이프라인 오류: {e}")
        return {"error": "추천 상품을 찾는 중 오류가 발생했습니다."}
