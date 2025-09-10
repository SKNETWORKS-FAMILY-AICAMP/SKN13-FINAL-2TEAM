# -*- coding: utf-8 -*-
# Stage 1: 이미지 → GPT-4o-mini 태깅 → caption1/caption2 분리 → 임베딩 → dict 반환 (skirt 전용)
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
    fclip.to(device)
except Exception:
    pass

# ================== GPT 프롬프트 ==================
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

# ================== 토큰 키 (15개) ==================
TOK_KEYS = [
    "color.main","color.sub","color.tone","pattern","pattern_scale",
    "material.fabric","silhouette","pleated","flare_level","wrap",
    "closure","details.pockets","details.slit","details.hem_finish",
    "style"
]

# ----------------------- 유틸 ----------------------
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import nest_asyncio; nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)

def image_to_b64(image_path: str, max_side: int = MAX_SIDE, jpeg_quality: int = JPEG_QUALITY):
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    scale = max(w, h) / float(max_side)
    if scale > 1.0:
        try: resample = Image.Resampling.BICUBIC
        except AttributeError: resample = Image.BICUBIC
        im = im.resize((int(w/scale), int(h/scale)), resample)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"

# 카테고리/타입 매핑 (ko → en)
def map_categories_to_en(major: str, sub: str) -> Tuple[str, str]:
    def norm(x: str) -> str:
        return (x or "").replace(" ", "").replace("/", "").replace("-", "").strip().lower()
    major_map = {"스커트": "skirt"}
    sub_map = {
        "미니스커트":"miniskirt",
        "미디스커트":"midiskirt",
        "롱스커트":"longskirt"
    }
    major_en = major_map.get(norm(major), "skirt")
    type_en  = sub_map.get(norm(sub), "unknown")
    return major_en, type_en

# 캡션 정규화
def normalize_caption_15(text: str) -> str:
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

def tokens_to_combined_text(tokens_csv: str, category: str, type_: str) -> str:
    vals = [p.strip() for p in tokens_csv.split(",")]
    fixed = []
    for i, tok in enumerate(vals):
        if "=" in tok:
            fixed.append(tok)
        else:
            fixed.append(f"{TOK_KEYS[i]}={tok}")
    return f"category={category} | type={type_} | " + " | ".join(fixed)

# caption1, caption2 분리
def split_caption(combined_text: str) -> Tuple[str, str]:
    if not combined_text:
        return "", ""
    parts = [p.strip() for p in combined_text.split("|")]
    caption1_keys = [
        "category", "type", "skirt.length", "silhouette",
        "material.fabric", "pattern", "pattern_scale",
        "color.main", "color.sub", "color.tone"
    ]
    caption1, caption2 = [], []
    for p in parts:
        key = p.split("=")[0].strip()
        if key in caption1_keys:
            caption1.append(p)
        else:
            caption2.append(p)
    return " | ".join(caption1), " | ".join(caption2)

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

# ---------- 공개 엔트리포인트 ----------
_BS = None

def determine_best_batch_size(start: int=64) -> int: 
    """
    OOM 피하면서 가장 큰 batch_size 선택 (1회만 탐색 후 캐시)
    CPU 환경에서는 16~64 권장. 상황 따라 Variable로 조정해도 좋음.
    """
    global _BS
    if _BS is not None: 
        return _BS
    
    candidates = [start, 48, 32, 24, 16, 12, 8, 4, 2, 1]
    if start not in candidates and start > 0:
        candidates = [start] + candidates

    try :
        with torch.no_grad():
            _ = fclip.encode_text(["warmup"] * candidates[0], batch_size=candidates[0])
            dummy = Image.new("RGB", (224,224), (255,255,255))
            _ = fclip.encode_images([dummy] * candidates[0], batch_size=candidates[0])
        _BS = candidates[0]
        return _BS 
    except Exception:
        pass 

    for bs in candidates: 
        try: 
            with torch.no_grad(): 
                _ = fclip.encode_text(['warmup'] * bs, batch_size=bs)
                dummy = Image.new("RGB", (224,224),(255,255,255))
                _ = fclip.encode_images([dummy] * bs, batch_size=bs)
            _BS = bs 
            return _BS 
        except Exception: 
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            continue
    
    _BS = 1 
    return _BS


# ---------- GPT 태깅 ----------
async def _gpt_tag_one(image_path:str) -> str:
    b64, mime = image_to_b64(image_path)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        ]
    }]
    resp = await aclient.chat.completions.create(
        model=MODEL, messages=messages,
        max_tokens=200, temperature=0.0, top_p=1.0, seed=12345
    )
    caption = resp.choices[0].message.content.strip()
    return normalize_caption_15(caption)

# ---------- 공개 API ----------
def process_batch(items: List[Tup[str,str,str,str]], gpt_concurrency:int=4) -> List[Dict]:
    if not items:
        return []

    # 1) GPT 태깅
    async def gather_all():
        sem = asyncio.Semaphore(max(1, gpt_concurrency))
        results = [None] * len(items)
        async def worker(i,image_path):
            async with sem:
                try:
                    cap15 = await _gpt_tag_one(image_path)
                except Exception:
                    cap15 = ",".join([f'{k}=unknown' for k in TOK_KEYS])
                results[i] = cap15
        await asyncio.gather(*[asyncio.create_task(worker(i, p[0])) for i,p in enumerate(items)])
        return results
    cap15_list: List[str] = run_async(gather_all())

    # 2) 텍스트/이미지 준비
    texts_combined, texts1, texts2, images, metas = [], [], [], [], []
    for cap15, (image_path, product_id, category_kr, type_kr) in zip(cap15_list, items):
        try:
            major_en, type_en = map_categories_to_en(category_kr, type_kr)
            combined_text = tokens_to_combined_text(cap15, major_en, type_en)
            c1, c2 = split_caption(combined_text)
            im = Image.open(image_path).convert("RGB")
        except Exception:
            continue
        texts_combined.append(combined_text)
        texts1.append(c1)
        texts2.append(c2)
        images.append(im)
        metas.append((str(product_id), major_en, type_en))
    if not texts_combined:
        return []

    # 3) 임베딩
    bs = determine_best_batch_size(64)
    with torch.no_grad():
        t1 = fclip.encode_text(texts1, batch_size=bs)
        t2 = fclip.encode_text(texts2, batch_size=bs)
        v  = fclip.encode_images(images, batch_size=bs)

    t1_np, t2_np, v_np = _to_numpy_2d(t1), _to_numpy_2d(t2), _to_numpy_2d(v)
    text_only = l2_normalize((t1_np + t2_np) / 2)
    multi = l2_normalize(0.5 * text_only + 0.5 * l2_normalize(v_np))

    # 4) 결과 반환
    out = []
    for (pid, major_en, type_en), info, t_vec, m_vec in zip(metas, texts_combined, text_only, multi):
        out.append({
            "id": pid,
            "category": major_en,
            "type": type_en,
            "information": info,
            "text": json.dumps(t_vec.tolist()),
            "multi": json.dumps(m_vec.tolist())
        })
    return out
