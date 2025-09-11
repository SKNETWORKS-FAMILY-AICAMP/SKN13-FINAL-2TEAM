# -*- coding: utf-8 -*-
import os, io, json, base64, asyncio
from typing import Tuple, Dict, List
import numpy as np
from PIL import Image
import torch
from openai import AsyncOpenAI
from fashion_clip.fashion_clip import FashionCLIP

# ---------- 설정 ----------
MODEL = "gpt-4o-mini"
ALPHA = 0.5

# OpenAI 클라이언트
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

# ================== GPT 프롬프트 (바지 16토큰) ==================
PROMPT = '''
You are a fashion vision tagger for fashion product retrieval.
Analyze ONLY the pants region even if other items/body parts are visible.
Never infer hidden details; if not clearly visible, output "unknown".
If not applicable, output "none".
Ignore tops, footwear, accessories, or background items. Only describe the pants themselves.
IMPORTANT: Do NOT output product category (e.g., denim/jogger/slacks/…). These are provided externally.

OUTPUT
Return ONE line with EXACTLY 16 lowercase, comma-separated tokens as key=value pairs,
using these keys IN THIS ORDER (keys must match exactly; no extra fields):

1) fit
   skinny / slim / straight / tapered / wide / relaxed / bootcut / flared / loose / unknown
2) rise
   low / mid / high / unknown
3) waistband
   fixed / elastic / drawstring / elastic+drawstring / unknown
4) closure
   zipper / buttons / drawstring / none / unknown
5) cuffs
   none / elastic / rib / rolled / raw / zipped / unknown
6) front.structure
   flat-front / pleated-single / pleated-double / darts-only / unknown
7) pockets.style
   5-pocket / slant / welt / patch / cargo / zip / none / unknown
8) pockets.secure
   none / button / zip / flap / mixed / unknown
9) material.fabric
   denim / jersey / fleece / woven-cotton / twill / corduroy / woven-poly / nylon / ripstop / wool-blend / leather / satin / other / unknown
10) denim.wash
   raw / dark-wash / mid-wash / light-wash / acid-wash / stone-wash / bleach / coated / colored / whiskered-faded / distressed / clean / none / unknown
   (if material.fabric ≠ denim ⇒ set to "none")
11) pattern
   solid / stripe / check / houndstooth / herringbone / dot / floral / paisley / animal / camouflage / text / scenic / logo / geometric / abstract / lace-knit / mixed / unknown
12) pattern_scale
   small / medium / large / none / unknown (if pattern=solid ⇒ none)
13) color.main
   black / white / gray / beige / cream / brown / navy / blue / green / yellow / orange / red / pink / purple / unknown
14) color.sub
   second-most color on the pants (≥15% of pant area) else none
15) leg.length
   shorts / cropped / ankle / full / unknown
16) hem.opening
   narrow / regular / wide / unknown
'''

# ================== 토큰 키 (PANTS 16개) ==================
TOK_KEYS = [
    "fit","rise","waistband","closure","cuffs","front.structure",
    "pockets.style","pockets.secure","material.fabric","denim.wash",
    "pattern","pattern_scale","color.main","color.sub","leg.length","hem.opening"
]

# ================== 허용값/별칭 (캡션 정규화에 필요) ==================
ALLOWED_PATTERN = {
    "solid","stripe","check","houndstooth","herringbone","dot","floral","paisley",
    "animal","camouflage","text","scenic","logo","geometric","abstract","lace-knit","mixed","unknown"
}
PATTERN_ALIASES = {
    "newspaper":"text","typographic":"text","letters":"text","letter":"text","textual":"text","script":"text","font":"text",
    "city":"scenic","building":"scenic","buildings":"scenic","map":"scenic","landmark":"scenic","architecture":"scenic",
    "chevron":"herringbone",
    "animal print":"animal","leopard":"animal","zebra":"animal","snake":"animal","giraffe":"animal","cow":"animal","tiger":"animal",
    "camo":"camouflage","military":"camouflage",
    "monogram":"logo"
}
ALLOWED_PATSCALE = {"small","medium","large","none","unknown"}
ALLOWED_COLOR = {"black","white","gray","beige","cream","brown","navy","blue","green","yellow","orange","red","pink","purple","unknown"}
ALLOWED_FIT = {"skinny","slim","straight","tapered","wide","relaxed","bootcut","flared","loose","unknown"}
ALLOWED_RISE = {"low","mid","high","unknown"}
ALLOWED_WAISTBAND = {"fixed","elastic","drawstring","elastic+drawstring","unknown"}
ALLOWED_CLOSURE = {"zipper","buttons","drawstring","none","unknown"}
ALLOWED_CUFFS = {"none","elastic","rib","rolled","raw","zipped","unknown"}
ALLOWED_FRONT = {"flat-front","pleated-single","pleated-double","darts-only","unknown"}
ALLOWED_POCKET_STYLE = {"5-pocket","slant","welt","patch","cargo","zip","none","unknown"}
ALLOWED_POCKET_SECURE = {"none","button","zip","flap","mixed","unknown"}
ALLOWED_FABRIC = {"denim","jersey","fleece","woven-cotton","twill","corduroy","woven-poly","nylon","ripstop","wool-blend","leather","satin","other","unknown"}
ALLOWED_DENIM_WASH = {"raw","dark-wash","mid-wash","light-wash","acid-wash","stone-wash","bleach","coated","colored","whiskered-faded","distressed","clean","none","unknown"}
ALLOWED_LENGTH = {"shorts","cropped","ankle","full","unknown"}
ALLOWED_HEMOPEN = {"narrow","regular","wide","unknown"}

# ================== 핵심 헬퍼 함수들 ==================

def _nz(s: str) -> str:
    return (s or "").strip().lower()

def _normalize_pattern_value(p: str) -> str:
    p = _nz(p)
    p = PATTERN_ALIASES.get(p, p)
    return p if p in ALLOWED_PATTERN else "unknown"

def map_categories_to_en(major: str, sub: str) -> Tuple[str, str]:
    def norm(x: str) -> str:
        return (x or "").replace(" ", "").replace("/", "").replace("-", "").strip().lower()
    major_map = {"하의":"pants","바지":"pants"}
    sub_map = {
        "데님팬츠":"denim-pants",
        "트레이닝조거팬츠":"jogger-pants",
        "코튼팬츠":"cotton-pants",
        "슈트팬츠슬랙스":"slacks",
        "슈트슬랙스":"slacks",
        "숏팬츠":"short-pants",
        "레깅스":"leggings",
        "카고팬츠":"cargo-pants",
    }
    major_en = major_map.get(norm(major), "pants")
    type_en  = sub_map.get(norm(sub), "unknown")
    return major_en, type_en

def normalize_caption_pants16(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.splitlines()).strip().strip('"').strip("'")

    # key=value 형식과 value만 있는 형식 모두 처리
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

    if len(vals) < 16:
        vals += ["unknown"] * (16 - len(vals))
    elif len(vals) > 16:
        vals = vals[:16]

    i = {name: idx for idx, name in enumerate(TOK_KEYS)}

    def _in(x, allowed): 
        return x if x in allowed else "unknown"

    vals[i["fit"]] = _in(vals[i["fit"]], ALLOWED_FIT)
    vals[i["rise"]] = _in(vals[i["rise"]], ALLOWED_RISE)
    vals[i["waistband"]] = _in(vals[i["waistband"]], ALLOWED_WAISTBAND)
    vals[i["closure"]] = _in(vals[i["closure"]], ALLOWED_CLOSURE)
    vals[i["cuffs"]] = _in(vals[i["cuffs"]], ALLOWED_CUFFS)
    vals[i["front.structure"]] = _in(vals[i["front.structure"]], ALLOWED_FRONT)
    vals[i["pockets.style"]] = _in(vals[i["pockets.style"]], ALLOWED_POCKET_STYLE)
    vals[i["pockets.secure"]] = _in(vals[i["pockets.secure"]], ALLOWED_POCKET_SECURE)
    vals[i["material.fabric"]] = _in(vals[i["material.fabric"]], ALLOWED_FABRIC)

    if vals[i["material.fabric"]] != "denim":
        vals[i["denim.wash"]] = "none"
    else:
        vals[i["denim.wash"]] = _in(vals[i["denim.wash"]], ALLOWED_DENIM_WASH)

    vals[i["pattern"]] = _normalize_pattern_value(vals[i["pattern"]])
    if vals[i["pattern"]] == "solid":
        vals[i["pattern_scale"]] = "none"
    else:
        vals[i["pattern_scale"]] = _in(vals[i["pattern_scale"]], ALLOWED_PATSCALE)

    vals[i["color.main"]] = _in(vals[i["color.main"]], ALLOWED_COLOR)
    csub = _nz(vals[i["color.sub"]])
    vals[i["color.sub"]] = csub if (csub in ALLOWED_COLOR or csub == "none") else "unknown"

    vals[i["leg.length"]] = _in(vals[i["leg.length"]], ALLOWED_LENGTH)
    vals[i["hem.opening"]] = _in(vals[i["hem.opening"]], ALLOWED_HEMOPEN)

    # 일관성 보정
    if vals[i["waistband"]] in {"elastic","elastic+drawstring"} and vals[i["closure"]] in {"zipper","buttons"}:
        vals[i["closure"]] = "unknown"
    if vals[i["hem.opening"]] == "unknown":
        if vals[i["fit"]] in {"flared","bootcut"}:
            vals[i["hem.opening"]] = "wide"
        elif vals[i["fit"]] in {"skinny","slim","tapered"}:
            vals[i["hem.opening"]] = "narrow"
    if vals[i["hem.opening"]] == "unknown" and vals[i["cuffs"]] in {"elastic","rib","zipped"}:
        vals[i["hem.opening"]] = "narrow"

    # 최종적으로 key=value 형태로 만들어 반환
    return ",".join(f"{k}={v}" for k, v in zip(TOK_KEYS, vals))


def _split_pants_attributes(tokens: List[str]) -> Tuple[List[str], List[str]]:
    caption1_attribute_keys = [
        "fit", "rise", "leg.length", "material.fabric", "pattern", 
        "pattern_scale", "color.main", "color.sub"
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
    return (x / np.maximum(n, eps)).astype(np.float32)

def _to_numpy_2d(x) -> np.ndarray:
    if isinstance(x, np.ndarray): return x
    elif torch.is_tensor(x): return x.detach().cpu().numpy()
    return np.asarray(x)

def combine_embeddings(text_emb: np.ndarray, img_emb: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    t = l2_normalize(text_emb); v = l2_normalize(img_emb)
    return l2_normalize(alpha * t + (1.0 - alpha) * v)

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
        return normalize_caption_pants16(raw_caption)

    try:
        cap16_csv = await _gpt_tag_single_bytes(image_bytes)
    except Exception:
        cap16_csv = ",".join([f'{k}=unknown' for k in TOK_KEYS])

    major_en, type_en = map_categories_to_en(category_kr, type_kr)
    attribute_tokens = [p.strip() for p in cap16_csv.split(",")]
    attr_parts1, attr_parts2 = _split_pants_attributes(attribute_tokens)

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