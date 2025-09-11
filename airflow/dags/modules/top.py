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
    fclip.to(device)
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

# # 파일명에서 product_id 추출 — tops 접두 허용
# PID_FROM_NAME = re.compile(r"^crop_top_([^.\\/]+)", re.IGNORECASE)
# def extract_product_id_from_filename(path: str) -> str:
#     base = os.path.basename(path)
#     m = PID_FROM_NAME.search(base)
#     return (m.group(1) if m else "").strip().lower()

# # 제품 CSV 불러오기 (상의만)
# def load_tops_map(csv_path: str) -> Dict[str, Tuple[str,str]]:
#     df = pd.read_csv(csv_path, dtype=str).fillna("")
#     df = df.apply(lambda col: col.str.strip().str.lower())
#     df_tops = df[df["대분류"].isin(["상의"])]
#     return dict(zip(df_tops["상품코드"], zip(df_tops["대분류"], df_tops["소분류"])))

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
        "category", "type", "color.main", "color.sub", 
        "pattern", "pattern_scale", "material.fabric"
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

# =========================================================
# 내부: GPT 태깅 (단건, async)
# =========================================================
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
        max_tokens=200, temperature=0.0, top_p=1.0,seed=12345 
    )
    caption = resp.choices[0].message.content.strip()
    return normalize_caption_top18(caption)

# =========================================================
# 공개 배치 API: process_batch
# =========================================================
def process_batch(items: List[Tup[str,str,str,str]], gpt_concurrency:int=4) -> List[Dict]: 
    """
    items: [(image_path, product_id, category_kr, type_kr), ...]
    1) 각 이미지 GPT 태깅(동시 처리)
    2) cap18 → (ko→en 매핑) → combined_text 리스트
    3) fclip.encode_text / encode_images 배치 임베딩
    4) dict 리스트 반환 (기존 process_one과 동일 필드)
    """
    if not items: 
        return []
    
    # 1) GPT 동시 태깅
    async def gather_all():
        sem = asyncio.Semaphore(max(1, gpt_concurrency))
        results = [None] * len(items)

        async def worker(i,image_path):
            async with sem: 
                try:
                    cap18 = await _gpt_tag_one(image_path)
                except Exception as e:
                    cap18 = ",".join([f'{k}=unknown' for k in TOK_KEYS])
                results[i] = cap18
            
        tasks = []
        for i, (image_path, _, _, _) in enumerate(items): 
            tasks.append(asyncio.create_task(worker(i, image_path)))
        await asyncio.gather(*tasks)
        return results
    
    cap18_list: List[str] = run_async(gather_all())

    # 2) combined_text / Image 로딩
    texts_combined, texts1, texts2, images, metas = [], [], [], [], []
    for cap18, (image_path, product_id, category_kr, type_kr) in zip(cap18_list, items):
        try:
            major_en, type_en = map_categories_to_en(category_kr, type_kr)
            combined_text = tokens_to_combined_text(cap18, major_en, type_en)
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
