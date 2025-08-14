from fastapi import APIRouter, Request, HTTPException, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from data_store import clothing_data
import urllib.parse
from db import get_db
from sqlalchemy.orm import Session
from crud.user_crud import get_user_by_username, list_jjim_product_ids, remove_jjim_bulk
from fastapi import Form
from fastapi.responses import JSONResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def jjim_list(request: Request, db: Session = Depends(get_db)):
    username = request.session.get("user_name")
    user = get_user_by_username(db, username)
    product_ids = list_jjim_product_ids(db, user.id) if user else []
    id_set = set(str(pid) for pid in product_ids)
    jjim_products = [p for p in clothing_data if str(p.get('상품ID')) in id_set]
    return templates.TemplateResponse("jjim/jjim.html", {"request": request, "jjim_products": jjim_products})


@router.post("/delete", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def delete_selected_jjim(request: Request, db: Session = Depends(get_db), product_ids: str = Form("")):
    # product_ids: comma-separated
    username = request.session.get("user_name")
    user = get_user_by_username(db, username)
    if not user:
        return {"success": False}
    ids = [pid.strip() for pid in product_ids.split(',') if pid.strip()]
    deleted = remove_jjim_bulk(db, user.id, ids)
    return {"success": True, "deleted": deleted}