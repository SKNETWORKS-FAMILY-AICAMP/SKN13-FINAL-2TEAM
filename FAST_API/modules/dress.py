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
    fclip.model.to(device)
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


# -------------------- 17-토큰 정규화(별칭/허용값 적용) ------------------------
def normalize_caption_dress17(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.splitlines()).strip().strip('"').strip("'")

    # 1. pants.py 스타일로 파싱: key=value 우선 처리
    parts = [p.strip().lower() for p in text.split(",") if p]
    vals = []
    temp_kv = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            temp_kv[k.strip()] = v.strip()
        else:
            vals.append(p)

    if temp_kv:
        vals = [temp_kv.get(k, "unknown") for k in TOK_KEYS]

    # 2. 토큰 개수 보정 (dress는 17개)
    if len(vals) < 17:
        vals += ["unknown"] * (17 - len(vals))
    elif len(vals) > 17:
        vals = vals[:17]

    # 3. 인덱스 생성 및 값 보정
    i = {name: idx for idx, name in enumerate(TOK_KEYS)}

    # pattern / pattern_scale
    vals[i["pattern"]] = _normalize_pattern_value(vals[i["pattern"]])
    if vals[i["pattern"]] == "solid":
        vals[i["pattern_scale"]] = "none"
    elif vals[i["pattern_scale"]] not in ALLOWED_PATSCALE:
        vals[i["pattern_scale"]] = "unknown"

    # colors
    if vals[i["color.main"]] not in ALLOWED_COLOR:
        vals[i["color.main"]] = "unknown"

    csub = _nz(vals[i["color.sub"]])
    vals[i["color.sub"]] = csub if (csub in ALLOWED_COLOR or csub == "none") else "unknown"

    # material
    mat = MATERIAL_ALIASES.get(_nz(vals[i["material.fabric"]]), _nz(vals[i["material.fabric"]]))
    vals[i["material.fabric"]] = mat if mat in ALLOWED_MATERIAL else "unknown"

    # hem.finish / slit
    if vals[i["hem.finish"]] not in ALLOWED_HEM_FINISH:
        vals[i["hem.finish"]] = "unknown"
    if vals[i["skirt.slit"]] not in ALLOWED_SLIT:
        vals[i["skirt.slit"]] = "unknown"

    # strapless / one-shoulder 규칙
    if vals[i["sleeve.length"]] == "strapless":
        vals[i["neckline"]] = "strapless"
        vals[i["sleeve.style"]] = "none"
    if vals[i["sleeve.length"]] == "one-shoulder":
        vals[i["neckline"]] = "one-shoulder"
        vals[i["sleeve.style"]] = "none"

    # 4. 최종적으로 key=value 형태로 만들어 반환
    return ",".join(f"{k}={v}" for k, v in zip(TOK_KEYS, vals))



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

# ---------- 임베딩 유틸 ----------
def _split_dress_attributes(tokens: List[str]) -> Tuple[List[str], List[str]]:
    caption1_attribute_keys = [
        "category", "type", "dress.length", "skirt.volume",
        "material.fabric", "pattern", "pattern_scale",
        "color.main", "color.sub"
    ]
    attrs1, attrs2 = [], []
    for part in tokens:
        key = part.split("=")[0].strip()
        if key in caption1_attribute_keys:
            attrs1.append(part)
        else:
            attrs2.append(part)
    return attrs1, attrs2

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
    async def _gpt_tag_single_bytes(img_bytes: bytes) -> str:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        messages = [{"role": "user", "content": [{"type": "text", "text": PROMPT}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]
        resp = await aclient.chat.completions.create(model=MODEL, messages=messages, max_tokens=180, temperature=0.0, top_p=1.0, seed=12345)

        # GPT의 원본 답변을 변수에 저장
        raw_caption = resp.choices[0].message.content.strip()
        
        # 원본 답변을 다음 함수로 전달
        return normalize_caption_dress17(raw_caption)

    try:
        cap17_csv = await _gpt_tag_single_bytes(image_bytes)
    except Exception:
        cap17_csv = ",".join([f'{k}=unknown' for k in TOK_KEYS])

    major_en, type_en = map_categories_to_en(category_kr, type_kr)
    attribute_tokens = [p.strip() for p in cap17_csv.split(",")]
    attr_parts1, attr_parts2 = _split_dress_attributes(attribute_tokens)

    base_info = [f"category={major_en}", f"type={type_en}"]
    text1 = " | ".join(base_info + attr_parts1)
    text2 = " | ".join(base_info + attr_parts2)
    full_information = " | ".join(base_info + attribute_tokens)
    print(f"Full combined caption: {full_information}")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    
    with torch.no_grad():
        text_embeddings_np = fclip.encode_text([text1, text2], batch_size=2)
        text_embeddings_tensor = torch.from_numpy(text_embeddings_np).to(device)
        avg_text_emb = torch.mean(text_embeddings_tensor, dim=0, keepdim=True)
        v_emb = fclip.encode_images([img], batch_size=1)

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