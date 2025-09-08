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
    fclip.to(device)
except Exception as e:
    print(f"FashionCLIP 모델을 디바이스({device})로 이동 중 오류: {e}")
    pass

# ================== Skirt용 토큰 키 (15개) ==================
TOK_KEYS = [
    "color.main","color.sub","color.tone","pattern","pattern_scale",
    "material.fabric","silhouette","pleated","flare_level","wrap",
    "closure","details.pockets","details.slit","details.hem_finish",
    "style"
]

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

# ----------------- 유틸리티 함수 (다른 모듈과 공통) -----------------
def normalize_caption_skirt15(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.splitlines()).strip().strip('"').strip("'")
    parts = [p.strip().lower() for p in text.split(",") if p]
    if len(parts) < 15:
        parts += ["unknown"] * (15 - len(parts))
    elif len(parts) > 15:
        parts = parts[:15]

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
    return ",".join(parts)

def tokens_to_combined_text(tokens_csv: str, category_en: str, type_en: str) -> str:
    fixed = []
    parts = [p.strip() for p in tokens_csv.split(",")]
    for i, tok in enumerate(parts):
        if "=" in tok: fixed.append(tok)
        else: fixed.append(f"{TOK_KEYS[i]}={tok}")
    return f"category={category_en} | type={type_en} | " + " | ".join(fixed)

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
    """
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

    major_en, type_en = map_categories_to_en(category_kr, type_kr)
    combined_text = tokens_to_combined_text(cap15, major_en, type_en)
    print(f"Combined Text: {combined_text}") # ADDED LOG
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None

    with torch.no_grad():
        t_emb = fclip.encode_text([combined_text], batch_size=1)
        v_emb = fclip.encode_images([img], batch_size=1)

    t_vec = l2_normalize(_to_numpy_2d(t_emb))[0]
    m_vec = combine_embeddings(_to_numpy_2d(t_emb), _to_numpy_2d(v_emb), alpha=ALPHA)[0]

    return {
        "id": product_id,
        "category": major_en,
        "type": type_en,
        "information": combined_text,
        "text": t_vec.tolist(),
        "multi": m_vec.tolist()
    }
