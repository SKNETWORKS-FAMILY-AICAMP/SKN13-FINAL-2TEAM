# -*- coding: utf-8 -*-
# Dress 전용: 이미지 → 태깅 → FashionCLIP 임베딩 → dict 반환 (Airflow에서 호출)

import os, io, json, base64, asyncio
from typing import Tuple, Dict, List, Tuple as Tup
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

# OpenAI 클라이언트 (환경변수 OPENAI_API_KEY 필요)
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

# ---------- 태깅 프롬프트 ----------
PROMPT = """
You are a vision tagger for fashion product retrieval.
Analyze ONLY the dress (one-piece) region even if other items/body parts are visible.
Never infer hidden details; if not clearly visible, output "unknown".
If not applicable, output "none".
Ignore hands, legs, accessories, or background items. Only describe the dress itself.

Return ONE line with EXACTLY 17 lowercase, comma-separated tokens as key=value pairs,
using these keys IN THIS ORDER (keys must match exactly; no extra fields):

1) bodice.fit
   fitted / semi / relaxed / unknown
2) skirt.volume
   slim / straight / a-line / full / mermaid / ball-gown / pencil / tulip / unknown
3) dress.length
   mini / knee / midi / ankle / maxi / unknown
4) hemline.shape
   straight / high-low / asymmetric / mermaid / ruffled / layered / wrap / train / handkerchief / bubble / shirttail / none / unknown
5) hem.finish
   clean / rolled / lettuce / scalloped / lace-trim / ruffle-trim / fringed / binding / raw / cutoff / pleated-hem / unknown
6) waistline
   none / natural / high / empire / drop / unknown
7) neckline
   round / v / square / halter / collar / off-shoulder / strapless / cowl / keyhole / boat / one-shoulder / unknown
8) sleeve.length
   sleeveless / cap / short / elbow / three-quarter / long / one-shoulder / strapless / unknown
9) sleeve.style
   none / puff / balloon / raglan / kimono / off-shoulder / cold-shoulder / bishop / roll-up / unknown
10) skirt.structure
   none / pleated / gathered / tiered / circle / bias / ruched / wrap / peplum / unknown
11) pattern
   solid / stripe / check / houndstooth / herringbone / dot / floral / paisley / animal / camouflage / text / scenic / logo / geometric / abstract / lace-knit / mixed / unknown
12) pattern_scale
   small / medium / large / none / unknown (if pattern=solid ⇒ none)
13) material.fabric
   cotton / linen / wool / silk / satin / denim / leather / suede / tweed / knit / rib-knit / lace / chiffon / tulle / velvet / corduroy / fleece / jersey / terry / seersucker / poplin / crepe / organza / brocade / jacquard / modal / rayon / viscose / lyocell / tencel / polyester / nylon / elastane / spandex / acrylic / pu / mesh / eyelet / crochet / faux-fur / faux-leather / blended / unknown
14) color.main
   black / white / gray / beige / cream / brown / navy / blue / green / yellow / orange / red / pink / purple / unknown
15) color.sub
   second-most ≥ ~15% else none
16) closure
   zipper / buttons / hooks / drawstring / none / unknown
17) skirt.slit
   none / front / side / back / two-side / high-slit / unknown

CONSISTENCY
- if pattern=solid ⇒ pattern_scale=none.
- if sleeve.length=strapless ⇒ neckline=strapless and sleeve.style=none.
- if sleeve.length=one-shoulder ⇒ neckline=one-shoulder and sleeve.style=none.
- hemline.shape describes the shape; hem.finish describes the finishing/trim; treat them independently.
- When unsure, output "unknown".

FORMAT RULES
- exactly 17 tokens
- all lowercase
- comma-separated
- each token must be key=value
- no explanations or extra words
"""

TOK_KEYS = [
    "bodice.fit","skirt.volume","dress.length","hemline.shape","hem.finish",
    "waistline","neckline","sleeve.length","sleeve.style","skirt.structure",
    "pattern","pattern_scale","material.fabric","color.main","color.sub","closure","skirt.slit"
]

# -------- 허용값 / 별칭 ---------
ALLOWED_PATTERNS = {
    "solid","stripe","check","houndstooth","herringbone","dot","floral","paisley",
    "animal","camouflage","text","scenic","logo","geometric","abstract","lace-knit","mixed","unknown"
}
PATTERN_ALIASES = {
    "newspaper":"text","typographic":"text","letters":"text","letter":"text","textual":"text","script":"text","font":"text",
    "city":"scenic","building":"scenic","map":"scenic","chevron":"herringbone",
    "animal print":"animal","leopard":"animal","zebra":"animal","snake":"animal","tiger":"animal","cow":"animal",
    "camo":"camouflage","monogram":"logo","heather":"abstract","marled":"abstract","tie-dye":"abstract","ikat":"abstract"
}
ALLOWED_PATSCALE = {"small","medium","large","none","unknown"}
ALLOWED_COLOR = {"black","white","gray","beige","cream","brown","navy","blue","green","yellow","orange","red","pink","purple","unknown"}
ALLOWED_HEM_FINISH = {"clean","rolled","lettuce","scalloped","lace-trim","ruffle-trim","fringed","binding","raw","cutoff","pleated-hem","unknown"}
ALLOWED_SLIT = {"none","front","side","back","two-side","high-slit","unknown"}
ALLOWED_MATERIAL = {
    "cotton","linen","wool","silk","satin","denim","leather","suede","tweed","knit","rib-knit",
    "lace","chiffon","tulle","velvet","corduroy","fleece","jersey","terry","seersucker","poplin",
    "crepe","organza","brocade","jacquard","modal","rayon","viscose","lyocell","tencel",
    "polyester","nylon","elastane","spandex","acrylic","pu","mesh","eyelet","crochet",
    "faux-fur","faux-leather","blended","unknown"
}
MATERIAL_ALIASES = {
    "poly":"polyester","polyamide":"nylon","spandex":"elastane","elastan":"elastane","lycra":"elastane",
    "pleather":"faux-leather","fake leather":"faux-leather","artificial leather":"faux-leather",
    "tencel™":"tencel","viscosa":"viscose","modal rayon":"modal","cotten":"cotton"
}

# ----------------- 유틸 -----------------
def _nz(s: str) -> str:
    return (s or "").strip().lower()

def _normalize_pattern_value(p: str) -> str:
    p = _nz(p)
    p = PATTERN_ALIASES.get(p, p)
    return p if p in ALLOWED_PATTERNS else "unknown"

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

# -------------------- 17-토큰 정규화(별칭/허용값 적용) ------------------------
def normalize_caption_dress17(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(str(text).splitlines()).strip().strip('"').strip("'").lower()
    raw_parts = [p.strip() for p in text.split(",") if p and len(p.strip()) > 0]
    kv_map = {}
    seq_idx = 0
    for tok in raw_parts:
        if "=" in tok:
            k, v = tok.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in TOK_KEYS and k not in kv_map:
                kv_map[k] = v
        else:
            while seq_idx < len(TOK_KEYS) and TOK_KEYS[seq_idx] in kv_map:
                seq_idx += 1
            if seq_idx < len(TOK_KEYS):
                kv_map[TOK_KEYS[seq_idx]] = tok
                seq_idx += 1
    parts = [kv_map.get(k, "unknown") for k in TOK_KEYS]
    IDX = {k:i for i,k in enumerate(TOK_KEYS)}

    # 2) 별칭/허용값 보정
    # pattern / pattern_scale
    parts[IDX["pattern"]] = _normalize_pattern_value(parts[IDX["pattern"]])
    if parts[IDX["pattern"]] == "solid":
        parts[IDX["pattern_scale"]] = "none"
    elif parts[IDX["pattern_scale"]] not in ALLOWED_PATSCALE:
        parts[IDX["pattern_scale"]] = "unknown"

    # colors
    if parts[IDX["color.main"]] not in ALLOWED_COLOR:
        parts[IDX["color.main"]] = "unknown"
    if parts[IDX["color.sub"]] not in ALLOWED_COLOR and parts[IDX["color.sub"]] != "none":
        parts[IDX["color.sub"]] = "unknown"

    # material
    mat = MATERIAL_ALIASES.get(_nz(parts[IDX["material.fabric"]]), _nz(parts[IDX["material.fabric"]]))
    parts[IDX["material.fabric"]] = mat if mat in ALLOWED_MATERIAL else "unknown"

    # hem.finish / slit
    if parts[IDX["hem.finish"]] not in ALLOWED_HEM_FINISH:
        parts[IDX["hem.finish"]] = "unknown"
    if parts[IDX["skirt.slit"]] not in ALLOWED_SLIT:
        parts[IDX["skirt.slit"]] = "unknown"

    # strapless / one-shoulder 규칙
    if parts[IDX["sleeve.length"]] == "strapless":
        parts[IDX["neckline"]] = "strapless"
        parts[IDX["sleeve.style"]] = "none"
    if parts[IDX["sleeve.length"]] == "one-shoulder":
        parts[IDX["neckline"]] = "one-shoulder"
        parts[IDX["sleeve.style"]] = "none"

    return ",".join(parts)

def tokens_to_combined_text(tokens_csv: str, category_en: str, type_en: str) -> str:
    fixed = []
    parts = [p.strip() for p in tokens_csv.split(",")]
    for i, tok in enumerate(parts):
        if "=" in tok: fixed.append(tok)
        else: fixed.append(f"{TOK_KEYS[i]}={tok}")
    return f"category={category_en} | type={type_en} | " + " | ".join(fixed)

# ----- 한→영 매핑 (원피스 전용) -----
def map_categories_to_en(major_ko: str, sub_ko: str) -> Tuple[str, str]:
    major_map = {"원피스": "dress"}
    sub_map = {
        "미니원피스": "minidress",
        "미디원피스": "mididress",
        "맥시원피스": "maxidress",
    }
    major_en = major_map.get(major_ko or "", "unknown")
    type_en  = sub_map.get(sub_ko or "", "unknown")
    return major_en, type_en

# caption1, caption2 분리
def split_caption(combined_text: str) -> Tuple[str, str]:
    if not combined_text:
        return "", ""
    parts = [p.strip() for p in combined_text.split("|")]
    caption1_keys = [
        "category", "type", "dress.length", "skirt.volume",
        "material.fabric", "pattern", "pattern_scale",
        "color.main", "color.sub"
    ]
    caption1, caption2 = [], []
    for p in parts:
        key = p.split("=")[0].strip()
        if key in caption1_keys:
            caption1.append(p)
        else:
            caption2.append(p)
    return " | ".join(caption1), " | ".join(caption2)

# ---------- 임베딩 유틸 ----------
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


# ---------- 배치용: 안전 배치 찾기 ----------
_BS: int | None = None

def determine_best_batch_size(start: int = 64) -> int:
    """
    OOM 피하면서 가장 큰 batch_size 선택 (1회 탐색 후 캐시)
    CPU 환경에선 16~64 권장
    """
    global _BS
    if _BS is not None:
        return _BS

    candidates = [start, 48, 32, 24, 16, 12, 8, 4, 2, 1]
    if start not in candidates and start > 0:
        candidates = [start] + candidates

    try:
        with torch.no_grad():
            _ = fclip.encode_text(["warmup"] * candidates[0], batch_size=candidates[0])
            dummy = Image.new("RGB", (224, 224), (255, 255, 255))
            _ = fclip.encode_images([dummy] * candidates[0], batch_size=candidates[0])
        _BS = candidates[0]
        return _BS
    except Exception:
        pass

    for bs in candidates:
        try:
            with torch.no_grad():
                _ = fclip.encode_text(["warmup"] * bs, batch_size=bs)
                dummy = Image.new("RGB", (224, 224), (255, 255, 255))
                _ = fclip.encode_images([dummy] * bs, batch_size=bs)
            _BS = bs
            return _BS
        except Exception:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            continue

    _BS = 1
    return _BS



# ---------------------- 내부: GPT 태깅 (단건, async) ----------------------
async def _gpt_tag_one(image_path: str) -> str:
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
    return normalize_caption_dress17(caption)

# ---------------------- 공개 배치 API ----------------------
def process_batch(items: List[Tup[str, str, str, str]], gpt_concurrency: int = 4) -> List[Dict]:
    """
    items: [(image_path, product_id, category_kr, type_kr), ...]
    1) 각 이미지 GPT 태깅(동시)
    2) cap17 → (ko→en 매핑) → combined_text 리스트
    3) F-CLIP 배치 임베딩
    4) dict 리스트 반환 (process_one과 동일 필드)
    """
    if not items:
        return []

    # 1) GPT 동시 태깅
    async def gather_all():
        sem = asyncio.Semaphore(max(1, gpt_concurrency))
        results = [None] * len(items)
        async def worker(i: int, image_path: str):
            async with sem:
                try:
                    cap17 = await _gpt_tag_one(image_path)
                except Exception:
                    cap17 = ",".join(f"{k}=unknown" for k in TOK_KEYS)
                results[i] = cap17
        tasks = []
        for i, (image_path, _, _, _) in enumerate(items):
            tasks.append(asyncio.create_task(worker(i, image_path)))
        await asyncio.gather(*tasks)
        return results
    cap17_list: List[str] = run_async(gather_all())

    # 2) combined_text / Image 로딩
    texts_combined, texts1, texts2, images, metas = [], [], [], [], []
    for cap17, (image_path, product_id, category_kr, type_kr) in zip(cap17_list, items):
        try:
            major_en, type_en = map_categories_to_en(category_kr, type_kr)
            combined_text = tokens_to_combined_text(cap17, major_en, type_en)
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
    

    # 4) 결과 dict 리스트로 반환
    out: List[Dict] = []
    for (pid, major_en, type_en), t_vec, m_vec, info in zip(metas, texts_combined, text_only, multi):
        out.append({
            "id": pid,
            "category": major_en,
            "type": type_en,
            "information": info,
            "text": json.dumps(t_vec.tolist()),
            "multi": json.dumps(m_vec.tolist())
        })
    return out