# -*- coding: utf-8 -*-
# Stage 1: 이미지 → GPT-4o-mini 태깅 → combined_text 생성 → dict 반환 (tops 전용)
import os, io, json, base64, asyncio, re
from typing import Tuple, Dict, List, Tuple as Tup
import pandas as pd
import numpy as np
from PIL import Image
import torch
from openai import AsyncOpenAI
from fashion_clip.fashion_clip import FashionCLIP

# ---------- 설정 ----------
MODEL = "gpt-4o-mini"
ALPHA = 0.5
MAX_SIDE = 768
JPEG_QUALITY = 85

aclient = AsyncOpenAI()

# 디바이스
if torch.cuda.is_available():
    device = "cuda"
elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
    device = "mps"
else:
    device = "cpu"

fclip = FashionCLIP("fashion-clip")
try:
    fclip.model.to(device)
except Exception:
    pass

# ================== GPT 프롬프트 ==================
PROMPT = """
You are a fashion vision tagger for tops (e.g., t-shirt, hoodie, blouse, sweater, sleeveless, athleisure).
Analyze ONLY the top garment. Ignore accessories, pants, skirts, skin, hair, or background.
If the attribute truly does not exist, output "none".

Return EXACTLY 18 lowercase, comma-separated tokens as key=value pairs,
using these keys IN THIS ORDER (keys must match exactly; no extra fields):

1) color.main
   black / white / gray / beige / cream / brown / navy / blue / green / yellow / orange / red / pink / purple / unknown
2) color.sub
   second-most visible (≥15% of garment area) else none
3) pattern
   solid / stripe / check / houndstooth / herringbone / dot / floral / paisley / animal / camouflage / text / scenic / logo / geometric / abstract / lace-knit / mixed / unknown
4) pattern_scale
   small / medium / large / none / unknown   (if pattern=solid ⇒ none)
5) material.fabric
   knit / denim / leather / suede / corduroy / chiffon / satin / lace / tweed / wool-blend / woven-cotton / woven-poly / other / unknown
6) sleeve.length
   sleeveless / short / half / three-quarter / long / unknown
7) sleeve.width
   slim / regular / wide / unknown
8) sleeve.style
   none / puff / balloon / raglan / kimono / off-shoulder / cold-shoulder / bishop / roll-up / spaghetti / tank / unknown
9) fit
   slim / regular / oversized / unknown
10) neckline
   round / v / square / halter / off-shoulder / strapless / cowl / one-shoulder / boat / unknown
11) collar
   none / shirt / polo / mandarin / high-neck / hood / unknown
12) closure
   zipper / buttons / hooks / drawstring / pullover / none / unknown
13) graphic
   none / logo / text / image / photo / art / abstract / all-over / unknown
14) graphic_position
   chest / sleeve / back / hem / multi / center / none / unknown
15) graphic_size
   small / medium / large / all-over / none / unknown
16) length.top
   cropped / regular / longline / tunic / unknown
17) sleeve.cuff
   plain / ribbed / elastic / buttoned / rolled / none / unknown
18) shoulder
   dropped / raglan / regular / padded / off-shoulder / one-shoulder / unknown

---

CONSISTENCY RULES
- if pattern=solid ⇒ pattern_scale=none
- if graphic=none ⇒ graphic_position=none and graphic_size=none
- if graphic=all-over ⇒ pattern=solid
- if pattern ≠ solid and graphic ≠ none ⇒ both can coexist (e.g., floral shirt with chest logo)
- if sleeve.length=sleeveless and sleeve.style in {spaghetti, tank} ⇒ keep both
- neckline and collar are independent; use none if not present
- When unsure, output "unknown"

---

FORMAT GUARD
- Exactly 18 tokens, lowercase, comma-separated
- key=value for every token
- No spaces around commas, no explanations
- Example:
  "color.main=white,color.sub=none,pattern=solid,pattern_scale=none,material.fabric=knit,sleeve.length=short,sleeve.width=regular,sleeve.style=none,fit=slim,neckline=round,collar=shirt,closure=buttons,graphic=logo,graphic_position=chest,graphic_size=small,length.top=regular,sleeve.cuff=ribbed,shoulder=regular"

"""

# ================== 토큰 키 (TOPS 18개) ==================
TOK_KEYS = [
    "color.main","color.sub","pattern","pattern_scale","material.fabric",
    "sleeve.length","sleeve.width","sleeve.style","fit","neckline","collar",
    "closure","graphic","graphic_position","graphic_size","length.top",
    "sleeve.cuff","shoulder"
]


# 카테고리/타입 매핑 (ko → en)
def map_categories_to_en(major: str, sub: str) -> Tuple[str, str]:
    def norm(x: str) -> str:
        return (x or "").replace(" ", "").replace("/", "").replace("-", "").strip().lower()
    major_map = {"상의":"top"}
    sub_map = {
        "후드티": "hoodie",
        "셔츠블라우스": "shirt-blouse",
        "긴소매": "longsleeve",
        "반소매": "shortsleeve",
        "피케카라": "polo",
        "니트스웨터": "knit-sweater",
        "슬리브리스": "sleeveless",
    }
    major_en = major_map.get(norm(major), "top")
    type_en  = sub_map.get(norm(sub), "unknown")
    return major_en, type_en

# 캡션 정규화 (18토큰)
def normalize_caption_top18(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.splitlines()).strip().strip('"').strip("'")

    # key=value 추출
    raw_parts = [p.strip().lower() for p in text.split(",") if "=" in p]
    kv_map = {}
    for p in raw_parts:
        if "=" in p:
            k, v = p.split("=", 1)
            kv_map[k.strip()] = v.strip()

    # 누락된 키 unknown 채우기
    fixed = []
    for k in TOK_KEYS:
        val = kv_map.get(k, "unknown")
        fixed.append(f"{k}={val}")

    # 룰 보정
    kv = {kv.split("=")[0]: kv.split("=")[1] for kv in fixed}
    if kv["pattern"] == "solid":
        kv["pattern_scale"] = "none"
    if kv["graphic"] == "none":
        kv["graphic_position"] = "none"
        kv["graphic_size"] = "none"

    return ",".join([f"{k}={kv[k]}" for k in TOK_KEYS])

def _split_top_attributes(tokens: List[str]) -> Tuple[List[str], List[str]]:
    """상의 18개 속성을 caption1, caption2 그룹으로 분리"""

    # caption1에 포함될 속성 키 리스트
    caption1_attribute_keys = [
        "color.main", "color.sub", "pattern", "pattern_scale", "material.fabric"
    ]

    attrs1, attrs2 = [], []
    for part in tokens:
        key = part.split("=")[0].strip()
        if key in caption1_attribute_keys:
            attrs1.append(part)
        else:
            attrs2.append(part)
    
    return attrs1, attrs2


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

# =========================================================
# 공개 단일 API: process_single_item (FastAPI용)
# =========================================================
async def process_single_item(image_bytes: bytes, product_id: str, category_kr: str, type_kr: str) -> Dict | None:
    """
    단일 이미지 바이트를 입력받아 임베딩을 생성.
    - image_bytes: 크롭된 이미지의 raw bytes
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
            max_tokens=200, temperature=0.0, top_p=1.0, seed=12345
        )
        caption = resp.choices[0].message.content.strip()
        return normalize_caption_top18(caption)

    try:
        cap18 = await _gpt_tag_single_bytes(image_bytes)
    except Exception as e:
        # GPT 태깅 실패 시, unknown으로 채워서 진행
        cap18 = ",".join([f'{k}=unknown' for k in TOK_KEYS])

    # 2) 캡션 분할
    major_en, type_en = map_categories_to_en(category_kr, type_kr)
    attribute_tokens = [p.strip() for p in cap18.split(",")]

    # 헬퍼 함수를 사용해 속성을 두 그룹으로 분리
    attr_parts1, attr_parts2 = _split_top_attributes(attribute_tokens)

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
        "information": full_information, # 정보용으로는 전체 캡션 저장
        "text": t_vec.tolist(),
        "multi": m_vec.tolist()
    }
