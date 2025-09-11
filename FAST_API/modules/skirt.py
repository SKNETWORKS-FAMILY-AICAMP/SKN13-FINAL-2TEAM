# -*- coding: utf-8 -*-
# Skirt 전용: 이미지 → 태깅 → FashionCLIP 임베딩 → dict 반환 (image_recommender에서 호출)

import os, io, json, base64, asyncio
from typing import Tuple, Dict, List
import numpy as np
from PIL import Image
import torch
from openai import AsyncOpenAI
from fashion_clip.fashion_clip import FashionCLIP

# ---------- 설정 ----------
MODEL = "gpt-4o-mini"
ALPHA = 0.5 # 텍스트-이미지 임베딩 결합 가중치

# OpenAI 클라이언트 (환경변수 OPENAI_API_KEY 필요)
aclient = AsyncOpenAI()

# 디바이스 설정
device = "cuda" if torch.cuda.is_available() else "cpu"

# FashionCLIP 모델 초기화
fclip = FashionCLIP("fashion-clip")
try:
    fclip.model.to(device)
except Exception as e:
    print(f"FashionCLIP 모델을 디바이스({device})로 이동 중 오류: {e}")
    pass

# ================== Skirt용 GPT 프롬프트 ==================
PROMPT = """
You are a vision tagger for fashion product retrieval.
Analyze ONLY the skirt region even if other items/body parts are visible.
Never infer hidden details.  
If an attribute is not clearly visible:
- For closure, details.pockets, details.slit: output "none"
- For all other attributes: output "unknown"

If the attribute truly does not exist, output "none".  
Ignore hands, legs, accessories, or background items. Only describe the skirt itself.

Return ONE line with EXACTLY 15 lowercase, comma-separated tokens as key=value pairs,
using these keys IN THIS ORDER (keys must match exactly; no extra fields):

1) color.main
   black / white / gray / beige / cream / brown / navy / blue / green / yellow / orange / red / pink / purple / unknown
2) color.sub
   second-most visible (≥15% of skirt area) else none
3) color.tone
   light / mid / dark / unknown
4) pattern
   solid / stripe / check / houndstooth / herringbone / dot / floral / paisley / animal / camouflage / text / scenic / logo / geometric / abstract / lace-knit / mixed / unknown
5) pattern_scale
   small / medium / large / none / unknown (if pattern=solid ⇒ none)
6) material.fabric
   knit / denim / leather / suede / corduroy / chiffon / satin / lace / tweed / wool-blend / woven-cotton / woven-poly / tulle / other / unknown
7) silhouette
   a-line / h-line / pencil / trumpet / mermaid / pleated / tulip / bubble / asymmetric / wrap / layered / gypsy / tiered / prairie / flounced / bias / draped / peplum / pant-skirt / slit / sarong / other / unknown
8) pleated
   yes / no / unknown
9) flare_level
   low / medium / high / none / unknown
10) wrap
   yes / no / unknown
11) closure
   zipper / buttons / hooks / drawstring / none / unknown
12) details.pockets
   cargo / welt / patch / none / unknown
13) details.slit
   front / side / back / none / unknown
14) details.hem_finish
   cutoff / clean / uneven / rolled / raw / unknown
15) style
   casual / formal / office / evening / street / school / sporty / unknown

---

CONSISTENCY RULES
- if pattern=solid ⇒ pattern_scale=none
- if silhouette=pleated ⇒ pleated=yes
- if pleated=yes but silhouette≠pleated ⇒ silhouette must not be "unknown"
- if wrap=yes ⇒ closure=none

---

FORMAT RULES
- Exactly 15 tokens, lowercase, comma-separated
- key=value for every token
- No extra words, no explanations
- Example valid output:
  "color.main=black,color.sub=none,color.tone=dark,pattern=solid,pattern_scale=none,material.fabric=chiffon,silhouette=pleated,pleated=yes,flare_level=high,wrap=no,closure=zipper,details.pockets=none,details.slit=side,details.hem_finish=clean,style=casual"

"""

# ================== Skirt용 토큰 키 (15개) ==================
TOK_KEYS = [
    "color.main","color.sub","color.tone","pattern","pattern_scale",
    "material.fabric","silhouette","pleated","flare_level","wrap",
    "closure","details.pockets","details.slit","details.hem_finish",
    "style"
]


# 카테고리/타입 매핑 (ko → en)
def map_categories_to_en(major_ko: str, sub_ko: str) -> Tuple[str, str]:
    major_map = {"스커트": "skirt"}

    sub_map = {
        "미니스커트": "miniskirt",
        "미디스커트": "midiskirt",
        "롱스커트": "longskirt",
    }
    major_en = major_map.get(major_ko or "", "unknown")
    type_en  = sub_map.get(sub_ko or "", "unknown")
    return major_en, type_en


# ----------------- 유틸리티 함수 (다른 모듈과 공통) -----------------
def normalize_caption_skirt15(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.splitlines()).strip().strip('"').strip("'")

    parts = [p.strip().lower() for p in text.split(",") if p]
    vals = []
    temp_kv = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            temp_kv[k.strip()] = v.strip()
        else:
            if len(vals) < len(TOK_KEYS):
                vals.append(p)
    
    if temp_kv:
        vals = [temp_kv.get(k, "unknown") for k in TOK_KEYS]
    
    if len(vals) < 15: vals += ["unknown"] * (15 - len(vals))
    elif len(vals) > 15: vals = vals[:15]

    i = {name: idx for idx, name in enumerate(TOK_KEYS)}

    if parts[i["pattern"]] == "solid":
        parts[i["pattern_scale"]] = "none"
    if parts[i["pleated"]] not in ("yes","no","unknown"):
        parts[i["pleated"]] = "unknown"
    if parts[i["wrap"]] not in ("yes","no","unknown"):
        parts[i["wrap"]] = "unknown"
    if parts[i["flare_level"]] not in ("low","medium","high","none","unknown"):
        parts[i["flare_level"]] = "unknown"
    if parts[i["details.slit"]] not in ("front","side","back","none","unknown"):
        parts[i["details.slit"]] = "unknown"
    if parts[i["details.hem_finish"]] not in ("cutoff","clean","uneven","rolled","raw","unknown"):
        parts[i["details.hem_finish"]] = "unknown"
    if parts[i["silhouette"]] == "pleated":
        parts[i["pleated"]] = "yes"
    if parts[i["wrap"]] == "yes":
        parts[i["closure"]] = "none"
    
    return ",".join(f"{k}={v}" for k, v in zip(TOK_KEYS, vals))

# ================== 임베딩 유틸 ================
def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1: x = x[None, :]
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n = np.maximum(n, eps)
    return (x / n).astype(np.float32)

def _to_numpy_2d(x) -> np.ndarray:
    if isinstance(x, np.ndarray): arr = x
    elif torch.is_tensor(x): arr = x.detach().cpu().numpy()
    else: arr = np.asarray(x)
    if arr.ndim == 1: arr = arr[None, :]
    return arr.astype(np.float32)

def combine_embeddings(text_emb: np.ndarray, img_emb: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    t = l2_normalize(text_emb); v = l2_normalize(img_emb)
    return l2_normalize(alpha*t + (1.0-alpha)*v)


def _split_skirt_attributes(tokens: List[str]) -> Tuple[List[str], List[str]]:
    """상의 18개 속성을 caption1, caption2 그룹으로 분리"""

    # caption1에 포함될 속성 키 리스트
    caption1_attribute_keys = [
        "category", "type", "skirt.length", "silhouette",
        "material.fabric", "pattern", "pattern_scale",
        "color.main", "color.sub", "color.tone"
    ]

    attrs1, attrs2 = [], []
    for part in tokens:
        key = part.split("=")[0].strip()
        if key in caption1_attribute_keys:
            attrs1.append(part)
        else:
            attrs2.append(part)
    
    return attrs1, attrs2


# =========================================================
# 공개 단일 API: process_single_item (FastAPI용)
# =========================================================
async def process_single_item(image_bytes: bytes, product_id: str, category_kr: str, type_kr: str) -> Dict | None:
    """
    단일 이미지 바이트를 입력받아 임베딩을 생성.
    """
    # 1) GPT 태깅 (비동기 실행)
    async def _gpt_tag_single_bytes(img_bytes: bytes) -> str:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        }]
        resp = await aclient.chat.completions.create(
            model=MODEL, messages=messages,
            max_tokens=160, # 스커트 토큰 수 유지
            temperature=0.0, top_p=1.0, seed=12345
        )
        caption = resp.choices[0].message.content.strip()
        return normalize_caption_skirt15(caption)

    try:
        cap15 = await _gpt_tag_single_bytes(image_bytes)
    except Exception as e:
        print(f"Skirt GPT 태깅 오류: {e}")
        cap15 = ",".join([f'{k}=unknown' for k in TOK_KEYS])

    # 2) 캡션 분할
    major_en, type_en = map_categories_to_en(category_kr, type_kr)
    attribute_tokens = [p.strip() for p in cap15.split(",")]

    # 헬퍼 함수를 사용해 속성을 두 그룹으로 분리
    attr_parts1, attr_parts2 = _split_skirt_attributes(attribute_tokens)

    # text1, text2 문자열 생성
    base_info = [f"category={major_en}", f"type={type_en}"]
    text1= " | ".join(base_info + attr_parts1)
    text2= " | ".join(base_info + attr_parts2)

    # 로깅 및 정보 저장용 전체 캡션
    full_information = " | ".join(base_info + attribute_tokens)
    print(f"Full combined caption: {full_information}")

    # 3) 이미지 로드
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    
    # 4) F-CLIP 임베딩 (분할 인코딩 및 평균)
    with torch.no_grad():
        # 두 캡션을 배치로 한번에 인코딩
        text_embeddings_np = fclip.encode_text([text1, text2],batch_size=2)

        # Numpy 배열을 Pytorch 텐서로 변환 
        text_embeddings_tensor = torch.from_numpy(text_embeddings_np).to(device)

        # 텍스트 임베딩 평균 계산
        avg_text_emb = torch.mean(text_embeddings_tensor,dim=0, keepdim=True)

        # 이미지 임베딩
        v_emb = fclip.encode_images([img], batch_size=1)

    # 5. 최종 임베딩 결합 및 반환
    t_vec = l2_normalize(_to_numpy_2d(avg_text_emb))[0]
    m_vec = combine_embeddings(_to_numpy_2d(avg_text_emb), _to_numpy_2d(v_emb), alpha=ALPHA)[0]

    return {
        "id": product_id,
        "category": major_en,
        "type": type_en,
        "information": full_information,
        "text": t_vec.tolist(),
        "multi": m_vec.tolist()
    }
