# -*- coding: utf-8 -*-
# Stage 1: 이미지 → GPT-4o-mini 태깅 → combined_text 생성
# - 결과 CSV: pants_caption.csv  (columns: product_id, combined_text)
# - category/type은 원본 CSV(pants.csv)에서 조회
# - pants (하의)만 처리
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
    fclip.to(device)
except Exception:
    pass

# ================== GPT 프롬프트 (바지 16토큰) ==================
PROMPT = """
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

---

SELECTION GUIDELINES
- fit: overall leg silhouette (tapered narrows to hem; straight stays constant; relaxed/loose is roomy; bootcut/flared widens from knee).
- rise: relative to natural waist (low <, high >; else mid). If covered by tops ⇒ unknown.
- waistband vs closure:
  elastic / elastic+drawstring ⇒ gathered stretch; drawstring shows a visible cord.
  fixed waist ⇒ usually zipper or buttons; if only a cord is visible ⇒ closure=drawstring.
- cuffs: rib/elastic bands ⇒ jogger-like; rolled = turn-ups; raw = cut-off fray; zipped = hem zippers.
- front.structure: flat-front (no pleats), pleated-single/double, darts-only (no visible pleats).
- pockets.style: 5-pocket (jeans layout), slant (chino/slacks), welt (back slit with welts), patch (sewn-on), cargo (large thigh), zip (visible zipper pockets).
  If multiple are equally present, prefer cargo > 5-pocket > slant > welt > patch > zip.
- material.fabric: pick the dominant cloth; coated denim is still denim (mark coating under denim.wash).
- denim.wash (DENIM ONLY): raw, dark-/mid-/light-wash; acid-/stone-/bleach; coated/colored; whiskered-faded; distressed; clean. If not denim ⇒ none.
- pattern vs wash: whiskers/fades/distressing are denim.wash, NOT pattern. pattern is prints/weaves (check, camo, stripe, etc.).
- pattern_scale: small < ~1/20; medium ~1/20–1/6; large > ~1/6 of visible leg height.
- colors: measure on pant area only (ignore belt/background/shoes).
- leg.length: shorts above knee; cropped noticeably above ankle; ankle around ankle bone; full covers ankle.
- hem.opening: the openness at hem relative to knee/thigh. flared/bootcut ⇒ typically wide; skinny/tapered ⇒ typically narrow.
- A small single brand logo patch/embroidery does not count as a pattern; keep pattern=solid unless logos repeat across the fabric.

---

CONSISTENCY RULES
- waistband ∈ {elastic, elastic+drawstring} without a fixed band ⇒ closure should be drawstring or none (avoid zipper/buttons unless clearly visible).
- if pattern=solid ⇒ pattern_scale=none (enforce).
- if material.fabric ≠ denim ⇒ denim.wash=none (enforce).
- fit vs hem.opening: if fit ∈ {flared, bootcut} and hem.opening is unknown ⇒ set hem.opening=wide. If fit ∈ {skinny, slim, tapered} and hem.opening is unknown ⇒ set hem.opening=narrow.
- cuffs ∈ {elastic, rib, zipped} with unknown hem.opening ⇒ prefer hem.opening=narrow.
- when attributes conflict and you cannot resolve, set the conflicting token(s) to "unknown".

---

PATTERN DISAMBIGUATION PRIORITY
animal > (stripe | check) > camouflage > logo > text > scenic
> (houndstooth | herringbone) > (floral | paisley) > (geometric | abstract) > lace-knit > solid.

---

FORMAT RULES
- Exactly 16 tokens, lowercase, comma-separated
- If <70% certain ⇒ unknown; if truly absent ⇒ none.
- Each token must be key=value
- No extra words, no explanations
- Example valid output:
  "fit=slim,rise=mid,waistband=fixed,closure=zipper,cuffs=none,front.structure=flat-front,pockets.style=5-pocket,pockets.secure=none,material.fabric=denim,denim.wash=mid-wash,pattern=solid,pattern_scale=none,color.main=blue,color.sub=none,leg.length=full,hem.opening=regular"

"""

# ================== 토큰 키 (PANTS 16개) ==================
TOK_KEYS = [
    "fit","rise","waistband","closure","cuffs","front.structure",
    "pockets.style","pockets.secure","material.fabric","denim.wash",
    "pattern","pattern_scale","color.main","color.sub","leg.length","hem.opening"
]

# ================== 허용값/별칭 ==================
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


# -----------------------유틸----------------------
def _nz(s: str) -> str:
    return (s or "").strip().lower()

def _normalize_pattern_value(p: str) -> str:
    p = _nz(p)
    p = PATTERN_ALIASES.get(p, p)
    return p if p in ALLOWED_PATTERN else "unknown"




# ================== 도우미 함수 ==================
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

# # 파일명에서 product_id 추출 — pants/jeans/shorts 접두 허용
# PID_FROM_NAME = re.compile(r"^(?:pants|jeans|shorts)_([^.\\/]+)", re.IGNORECASE)
# def extract_product_id_from_filename(path: str) -> str:
#     base = os.path.basename(path)
#     m = PID_FROM_NAME.search(base)
#     return (m.group(1) if m else "").strip().lower()

# # 제품 CSV 불러오기 (하의만)
# def load_pants_map(csv_path: str) -> Dict[str, Tuple[str,str]]:
#     df = pd.read_csv(csv_path, dtype=str)
#     df = df.fillna("").apply(lambda col: col.str.strip().str.lower())
#     # 대분류가 '하의' 또는 '바지'인 것만 사용
#     df_pants = df[df["대분류"].isin(["하의","바지"])]
#     return dict(zip(df_pants["상품코드"], zip(df_pants["대분류"], df_pants["소분류"])))

# 카테고리/타입 매핑 (ko → en)
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

# 캡션 정규화 (16토큰 값만 정규화; key=가 포함돼도 안전)
def normalize_caption_pants16(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.splitlines()).strip().strip('"').strip("'")
    parts = [p.strip().lower() for p in text.split(",") if p]

    # key=value가 들어왔으면 값만 추출
    vals = []
    for i, p in enumerate(parts):
        if "=" in p:
            k, v = p.split("=", 1)
            vals.append(v.strip())
        else:
            vals.append(p)

    # 패딩/트림
    if len(vals) < 16:
        vals += ["unknown"] * (16 - len(vals))
    elif len(vals) > 16:
        vals = vals[:16]

    # 인덱스
    i_fit, i_rise, i_waist, i_closure, i_cuffs, i_front = 0,1,2,3,4,5
    i_pstyle, i_psecure = 6,7
    i_fabric, i_wash = 8,9
    i_pat, i_pscale = 10,11
    i_cmain, i_csub = 12,13
    i_len, i_hem = 14,15

    def _in(x, allowed): return x if x in allowed else "unknown"

    vals[i_fit]     = _in(vals[i_fit], ALLOWED_FIT)
    vals[i_rise]    = _in(vals[i_rise], ALLOWED_RISE)
    vals[i_waist]   = _in(vals[i_waist], ALLOWED_WAISTBAND)
    vals[i_closure] = _in(vals[i_closure], ALLOWED_CLOSURE)
    vals[i_cuffs]   = _in(vals[i_cuffs], ALLOWED_CUFFS)
    vals[i_front]   = _in(vals[i_front], ALLOWED_FRONT)
    vals[i_pstyle]  = _in(vals[i_pstyle], ALLOWED_POCKET_STYLE)
    vals[i_psecure] = _in(vals[i_psecure], ALLOWED_POCKET_SECURE)
    vals[i_fabric]  = _in(vals[i_fabric], ALLOWED_FABRIC)

    # denim.wash
    wash = _nz(vals[i_wash])
    if vals[i_fabric] != "denim":
        wash = "none"
    elif wash not in ALLOWED_DENIM_WASH:
        wash = "unknown"
    vals[i_wash] = wash

    # 패턴/스케일
    pattern = _normalize_pattern_value(vals[i_pat])
    vals[i_pat] = pattern
    pscale = _nz(vals[i_pscale])
    if pattern == "solid":
        pscale = "none"
    elif pscale not in ALLOWED_PATSCALE:
        pscale = "unknown"
    vals[i_pscale] = pscale

    # 색상
    vals[i_cmain] = _in(vals[i_cmain], ALLOWED_COLOR)
    csub = _nz(vals[i_csub])
    vals[i_csub] = csub if (csub in ALLOWED_COLOR or csub == "none") else "unknown"

    # 길이/밑단
    vals[i_len] = _in(vals[i_len], ALLOWED_LENGTH)
    vals[i_hem] = _in(vals[i_hem], ALLOWED_HEMOPEN)

    # 일관성 보정
    if vals[i_waist] in {"elastic","elastic+drawstring"} and vals[i_closure] in {"zipper","buttons"}:
        vals[i_closure] = "unknown"
    if vals[i_hem] == "unknown":
        if vals[i_fit] in {"flared","bootcut"}: vals[i_hem] = "wide"
        elif vals[i_fit] in {"skinny","slim","tapered"}: vals[i_hem] = "narrow"
    if vals[i_hem] == "unknown" and vals[i_cuffs] in {"elastic","rib","zipped"}:
        vals[i_hem] = "narrow"

    return ",".join(vals)

def tokens_to_combined_text(tokens_csv: str, category: str, type_: str) -> str:
    parts = [p.strip() for p in tokens_csv.split(",")]
    fixed = []
    for i, tok in enumerate(parts):
        if "=" in tok: fixed.append(tok)
        else: fixed.append(f"{TOK_KEYS[i]}={tok}")
    return f"category={category} | type={type_} | " + " | ".join(fixed)


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

# ================== 배치 사이즈 오토 탐색 ==================
_BS = None
def determine_best_batch_size(start: int = 64) -> int:
    """
    OOM 피하면서 가장 큰 batch_size 선택 (1회만 탐색 후 캐시)
    CPU 환경: 대개 16~64; 상황에 따라 Variable로 조정해도 좋습니다.
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

# ================== 내부: GPT 태깅 (async 단건) ==================
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
        max_tokens=180, temperature=0.0, top_p=1.0, seed=12345
    )
    caption = resp.choices[0].message.content.strip()
    return normalize_caption_pants16(caption)

# ================== 공개 배치 API ==================
def process_batch(items: List[Tup[str, str, str, str]], gpt_concurrency: int = 4) -> List[Dict]:
    """
    items: [(image_path, product_id, category_kr, type_kr), ...]
    1) 각 이미지 GPT 태깅(동시 처리)
    2) cap16 → (ko→en 매핑) → combined_text 리스트
    3) FashionCLIP encode_text/encode_images 배치 임베딩
    4) dict 리스트 반환: id, category, type, information, text, multi
    """
    if not items:
        return []

    # 1) GPT 동시 태깅
    async def gather_all():
        sem = asyncio.Semaphore(max(1, gpt_concurrency))
        results = [None] * len(items)

        async def worker(i, image_path):
            async with sem:
                try:
                    cap16 = await _gpt_tag_one(image_path)
                except Exception:
                    cap16 = ",".join([f"{k}=unknown" for k in TOK_KEYS])
                results[i] = cap16

        tasks = []
        for i, (image_path, _, _, _) in enumerate(items):
            tasks.append(asyncio.create_task(worker(i, image_path)))
        await asyncio.gather(*tasks)
        return results

    cap16_list: List[str] = run_async(gather_all())

    # 2) combined_text / Image 로딩
    texts: List[str] = []
    images: List[Image.Image] = []
    metas: List[Tup[str, str, str]] = []

    for cap16, (image_path, product_id, category_kr, type_kr) in zip(cap16_list, items):
        try:
            major_en, type_en = map_categories_to_en(category_kr, type_kr)
            combined_text = tokens_to_combined_text(cap16, major_en, type_en)
            im = Image.open(image_path).convert("RGB")
        except Exception:
            continue
        texts.append(combined_text)
        images.append(im)
        metas.append((str(product_id), major_en, type_en))

    if not texts:
        return []

    # 3) F-CLIP 임베딩 (배치)
    bs = determine_best_batch_size(64)
    with torch.no_grad():
        t_emb = fclip.encode_text(texts, batch_size=bs)
        v_emb = fclip.encode_images(images, batch_size=bs)

    t_vecs = l2_normalize(_to_numpy_2d(t_emb))
    m_vecs = combine_embeddings(_to_numpy_2d(t_emb), _to_numpy_2d(v_emb), alpha=ALPHA)

    # 4) 결과 dict 리스트 반환
    out: List[Dict] = []
    for (pid, major_en, type_en), t_vec, m_vec, info in zip(metas, t_vecs, m_vecs, texts):
        out.append({
            "id": pid,
            "category": major_en,
            "type": type_en,
            "information": info,
            "text": json.dumps(t_vec.tolist()),
            "multi": json.dumps(m_vec.tolist())
        })
    return out

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
            max_tokens=180, temperature=0.0, top_p=1.0, seed=12345
        )
        caption = resp.choices[0].message.content.strip()
        return normalize_caption_pants16(caption)

    try:
        cap16 = await _gpt_tag_single_bytes(image_bytes)
    except Exception as e:
        cap16 = ",".join([f'{k}=unknown' for k in TOK_KEYS])

    # 2) combined_text 생성 및 이미지 로드
    major_en, type_en = map_categories_to_en(category_kr, type_kr)
    combined_text = tokens_to_combined_text(cap16, major_en, type_en)
    print(f"Combined Text: {combined_text}") # ADDED LOG
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None

    # 3) F-CLIP 임베딩 (단일 항목)
    with torch.no_grad():
        t_emb = fclip.encode_text([combined_text], batch_size=1)
        v_emb = fclip.encode_images([img], batch_size=1)

    t_vec = l2_normalize(_to_numpy_2d(t_emb))[0]
    m_vec = combine_embeddings(_to_numpy_2d(t_emb), _to_numpy_2d(v_emb), alpha=ALPHA)[0]

    # 4) 결과 dict로 반환
    return {
        "id": product_id,
        "category": major_en,
        "type": type_en,
        "information": combined_text,
        "text": t_vec.tolist(),
        "multi": m_vec.tolist()
    }