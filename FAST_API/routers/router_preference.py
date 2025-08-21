from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from data_store import clothing_data
from db import get_db
from sqlalchemy.orm import Session
from crud.user_crud import add_jjim, get_user_by_username
from fastapi import Form
from dependencies import login_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/api/items", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def get_preference_items(request: Request):
    import random
    items = random.sample(clothing_data, min(20, len(clothing_data))) if clothing_data else []
    return items

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def preference(request: Request):
    import random
    items = random.sample(clothing_data, min(20, len(clothing_data))) if clothing_data else []
    return templates.TemplateResponse(
        "preference/preference.html", 
        {"request": request, "recommended_items": items}
    )


@router.post("/jjim", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def add_to_jjim(request: Request, product_id: str = Form(...), db: Session = Depends(get_db)):
    username = request.session.get("user_name")
    user = get_user_by_username(db, username)
    if not user:
        return {"success": False, "message": "사용자 없음"}
    add_jjim(db, user.id, product_id)
    return {"success": True}