from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/reviews", tags=["reviews"])
templates = Jinja2Templates(directory="templates")
# ✅ 전역 더미 리뷰 리스트
dummy_reviews = [
    {"id": 1, "product": "기본 반팔 티셔츠", "rating": 4, "content": "시원하고 핏도 예뻐요!", "user": "무신사유저1"},
    {"id": 2, "product": "린넨 셔츠", "rating": 3, "content": "구김은 있지만 시원함은 최고!", "user": "여름룩러버"},
]

# ✅ 리뷰 목록 + 정렬
@router.get("/", response_class=HTMLResponse)
def review_list(request: Request, sort: str = "recent"):
    if sort == "rating_desc":
        sorted_reviews = sorted(dummy_reviews, key=lambda x: x["rating"], reverse=True)
    elif sort == "rating_asc":
        sorted_reviews = sorted(dummy_reviews, key=lambda x: x["rating"])
    else:
        sorted_reviews = dummy_reviews

    return templates.TemplateResponse("review/review_list.html", {
        "request": request,
        "reviews": sorted_reviews,
        "sort": sort,
    })

# ✅ 리뷰 작성 처리
@router.post("/create")
def create_review(
    product: str = Form(...),
    rating: int = Form(...),
    content: str = Form(...),
    author: str = Form(...)
):
    dummy_reviews.append({
        "id": len(dummy_reviews) + 1,
        "product": product,
        "rating": rating,
        "content": content,
        "user": author
    })
    return RedirectResponse(url="/reviews", status_code=302)

# ✅ 리뷰 상세 페이지
@router.get("/{review_id}", response_class=HTMLResponse)
def review_detail(request: Request, review_id: int):
    review = next((r for r in dummy_reviews if r["id"] == review_id), None)
    return templates.TemplateResponse("review/review_detail.html", {
        "request": request,
        "review": review
    })
