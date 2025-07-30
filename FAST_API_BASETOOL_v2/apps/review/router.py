# from fastapi import APIRouter, Request
# from fastapi.responses import HTMLResponse
# from fastapi.templating import Jinja2Templates

# router = APIRouter()
# templates = Jinja2Templates(directory="templates")

# @router.get("/", response_class=HTMLResponse)
# async def review(request: Request):
#     return templates.TemplateResponse("review.html", {"request": request})

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

dummy_reviews = [
    {"id": 1, "product": "반팔티", "rating": 5, "content": "완전 시원해요!", "user": "홍길동"},
    {"id": 2, "product": "셔츠", "rating": 3, "content": "핏은 좋아요", "user": "김철수"},
]

@router.get("/", response_class=HTMLResponse)
def review_list(request: Request):
    return templates.TemplateResponse("review/review_list.html", {
        "request": request,
        "reviews": dummy_reviews
    })

@router.get("/{review_id}", response_class=HTMLResponse)
def review_detail(request: Request, review_id: int):
    review = next((r for r in dummy_reviews if r["id"] == review_id), None)
    return templates.TemplateResponse("review/review_detail.html", {
        "request": request,
        "review": review
    })