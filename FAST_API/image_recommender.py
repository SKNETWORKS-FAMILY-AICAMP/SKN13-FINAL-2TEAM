import os
import tempfile
import logging
import boto3
import requests
from PIL import Image
import io
import importlib
import base64
import json

from ultralytics import YOLO
from qdrant_client import QdrantClient

# === 로거 설정 ===
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# === 환경 변수 및 설정 (보안을 위해 실제 값은 .env 파일 등에서 로드해야 함) ===
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
MODEL_KEY = os.getenv("S3_MODEL_KEY", "best.pt")
QDRANT_URL = os.getenv("QDRANT_URL", "http://43.201.185.192:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ivlle")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") # Qdrant API 키 추가
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === 모델 및 클라이언트 초기화 (싱글톤 패턴) ===
yolo_model = None
qdrant_client = None

def get_s3_client():
    """Boto3 S3 클라이언트를 생성합니다."""
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )

def get_yolo_model():
    """YOLO 모델을 S3에서 다운로드하여 로드합니다 (최초 1회)."""
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
    """Qdrant 클라이언트를 초기화합니다. API 키가 있으면 사용합니다."""
    global qdrant_client
    if qdrant_client is None:
        if QDRANT_API_KEY:
            logger.info("Qdrant 클라이언트 초기화 (API Key 사용)")
            qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60.0)
        else:
            logger.info("Qdrant 클라이언트 초기화 (API Key 없음)")
            qdrant_client = QdrantClient(url=QDRANT_URL, timeout=60.0)
    return qdrant_client


def classify_image_with_openai(image_bytes: bytes) -> dict:
    """OpenAI Vision API를 사용하여 이미지의 대분류/소분류를 추론합니다."""
    logger.info("OpenAI로 이미지 분류 시작...")

    # 각 모듈에서 sub_map 정보 추출
    # top.py
    top_sub_map = {
        "후드티": "hoodie", "셔츠블라우스": "shirt-blouse", "긴소매": "longsleeve",
        "반소매": "shortsleeve", "피케카라": "polo", "니트스웨터": "knit-sweater",
        "슬리브리스": "sleeveless",
    }
    # pants.py
    pants_sub_map = {
        "데님팬츠":"denim-pants", "트레이닝조거팬츠":"jogger-pants", "코튼팬츠":"cotton-pants",
        "슈트팬츠슬랙스":"slacks", "슈트슬랙스":"slacks", "숏팬츠":"short-pants",
        "레깅스":"leggings", "카고팬츠":"cargo-pants",
    }
    # dress.py
    dress_sub_map = {
        "미니원피스": "minidress", "미디원피스": "mididress", "맥시원피스": "maxidress",
    }

    # OpenAI에 보낼 프롬프트 구성
    prompt = f"""\
You are a fashion specialist AI. Analyze the user-uploaded image and identify the main clothing item.\n\n1.  First, determine the major category of the item. It must be one of ['top', 'pants', 'dress'].\n2.  Based on the major category, determine the most appropriate minor category from the corresponding list below.\n\n    - If the major category is 'top', choose one from: {list(top_sub_map.values())}\n    - If the major category is 'pants', choose one from: {list(pants_sub_map.values())}\n    - If the major category is 'dress', choose one from: {list(dress_sub_map.values())}\n\n3.  Return the result as a single, minified JSON object with two keys: "category" (the major category) and "type" (the minor category). Do not include any other text or explanations.\n\nExample response for a t-shirt image:\n{{\"category\":\"top\",\"type\":\"shortsleeve\"}}\n"""

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ],
                }
            ],
            max_tokens=100,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content
        logger.info(f"OpenAI API 응답 수신: {content}")
        
        result = json.loads(content)
        
        # 간단한 유효성 검사
        if "category" in result and "type" in result:
            logger.info(f"이미지 분류 완료: Category={result['category']}, Type={result['type']}")
            return result
        else:
            raise ValueError("OpenAI 응답에 'category' 또는 'type' 키가 없습니다.")

    except Exception as e:
        logger.error(f"OpenAI 이미지 분류 실패: {e}")
        # 실패 시 기본값 또는 에러 처리
        return {"category": "unknown", "type": "unknown"}


def crop_image_with_yolo(image_bytes: bytes, category: str) -> bytes | None:
    """\
YOLO 모델로 이미지에서 특정 카테고리의 객체를 찾아 크롭합니다.\n신뢰도 0.5 이상인 가장 확률이 높은 객체를 반환합니다.\n"""

    logger.info(f"YOLO 객체 탐지 시작 (타겟: {category})")
    model = get_yolo_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    LABEL_MAP = {"top": "top", "pants": "pants", "dress": "dress", "skirt": "skirt"}
    target_label = LABEL_MAP.get(category)
    if not target_label:
        logger.warning(f"지원하지 않는 카테고리입니다: {category}")
        return None

    results = model(img, conf=0.5, iou=0.45, verbose=False)
    
    best_detection = None
    for res in results:
        if res.boxes is None:
            continue
        for box, cls, conf in zip(res.boxes.xyxy, res.boxes.cls, res.boxes.conf):
            label = model.names[int(cls)].lower()
            confidence = float(conf)
            if label == target_label:
                if best_detection is None or confidence > best_detection[0]:
                    best_detection = (confidence, box)

    if best_detection is None:
        logger.warning(f"객체를 찾지 못했습니다 (타겟: {target_label}, 신뢰도 0.5 이상).")
        return None

    confidence, best_box = best_detection
    x1, y1, x2, y2 = map(int, best_box.tolist())
    cropped_img = img.crop((x1, y1, x2, y2))
    
    logger.info(f"YOLO 객체 탐지 및 크롭 완료 (신뢰도: {confidence:.2f})")
    
    # 크롭된 이미지를 bytes로 변환하여 반환
    buffer = io.BytesIO()
    cropped_img.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def get_embeddings_for_cropped_image(cropped_bytes: bytes, category: str, type: str) -> dict:
    """\
    크롭된 이미지와 텍스트 정보를 바탕으로 임베딩을 생성합니다.\n    embedding_pipeline2.py의 run_embeddings 태스크와 modules/ 로직을 참고합니다.\n    """

    logger.info(f"임베딩 생성 시작 (카테고리: {category}, 타입: {type})")
    MODULE_MAP = {"top": "modules.top", "pants": "modules.pants", "skirt": "modules.skirt", "dress": "modules.dress"}
    
    module_name = MODULE_MAP.get(category)
    if not module_name:
        raise ValueError(f"지원하지 않는 카테고리입니다: {category}")
        
    # OpenAI 키 설정
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

    try:
        module = importlib.import_module(module_name)
        if not hasattr(module, "process_single_item"):
             raise RuntimeError(f"모듈 '{module_name}'에 process_single_item 함수가 필요합니다.")

        # process_single_item 함수는 (image_bytes, product_id, category_kr, type_kr) 등을 인자로 받을 것으로 예상
        # 여기서는 단순화를 위해 image_bytes와 텍스트 정보만 전달
        embedding_result = module.process_single_item(cropped_bytes, "user_upload", category, type)
        logger.info("임베딩 생성 완료.")
        return embedding_result # {'text': [...], 'multi': [...]} 형태의 딕셔너리 예상
        
    except Exception as e:
        logger.error(f"임베딩 생성 중 오류 발생: {e}")
        raise

def search_similar_items_in_qdrant(embeddings: dict, limit: int = 5) -> list:
    """Qdrant에서 유사한 아이템을 검색합니다."""
    logger.info("Qdrant 유사도 검색 시작...")
    client = get_qdrant_client()
    
    # 'text'와 'multi' 벡터가 모두 있다면, 각각 검색 후 결과를 조합하거나 가중치를 둘 수 있습니다.
    # 여기서는 'multi' 벡터를 우선적으로 사용합니다.
    query_vector = embeddings.get("multi") or embeddings.get("text")
    if not query_vector:
        raise ValueError("유효한 쿼리 벡터가 없습니다.")

    # 검색 쿼리 실행
    # 'using' 파라미터로 어떤 벡터를 검색할지 지정
    search_result = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=("multi", query_vector), # 'multi' 벡터 인덱스에서 검색
        limit=limit,
        with_payload=True  # payload 정보(상품 메타데이터)도 함께 가져옴
    )
    
    logger.info(f"Qdrant 유사도 검색 완료. {len(search_result)}개 결과 수신.")
    
    # 결과 포맷팅
    recommendations = []
    for point in search_result:
        recommendations.append({
            "id": point.id,
            "score": point.score,
            **point.payload,
        })
        
    return recommendations

# === 메인 파이프라인 함수 ===

def recommend_by_image(image_bytes: bytes) -> dict:
    """\
    이미지 추천의 전체 파이프라인을 실행합니다.\n    """

    try:
        # 1. OpenAI로 이미지 분류 (카테고리/타입 식별)
        classification = classify_image_with_openai(image_bytes)
        category = classification["category"]
        item_type = classification["type"]

        # 2. YOLO로 객체 탐지 및 크롭
        cropped_bytes = crop_image_with_yolo(image_bytes, category)
        if not cropped_bytes:
            return {"error": "이미지에서 의류를 찾지 못했습니다. 다른 이미지를 사용해 주세요."}

        # 3. 크롭된 이미지로 임베딩 생성
        embeddings = get_embeddings_for_cropped_image(cropped_bytes, category, item_type)
        if not embeddings:
             return {"error": "이미지 특징을 추출하는 데 실패했습니다."}

        # 4. Qdrant에서 유사 아이템 검색
        recommendations = search_similar_items_in_qdrant(embeddings)
        
        return {"recommendations": recommendations, "information": embeddings.get("information")}

    except Exception as e:
        logger.exception(f"이미지 추천 파이프라인 오류: {e}")
        return {"error": "추천 상품을 찾는 중 오류가 발생했습니다."}