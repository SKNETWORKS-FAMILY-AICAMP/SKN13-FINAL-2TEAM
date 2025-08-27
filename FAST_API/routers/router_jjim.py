from fastapi import APIRouter, Request, HTTPException, Depends, Query
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from data_store import clothing_data, processed_clothing_data
import urllib.parse
from db import get_db
from sqlalchemy.orm import Session
from crud.user_crud import get_user_by_username, list_jjim_product_ids, remove_jjim_bulk
from fastapi import Form
from fastapi.responses import JSONResponse
from typing import List

from typing import List, Optional # Import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def jjim_list(request: Request, db: Session = Depends(get_db)):
    username = request.session.get("user_name")
    user = get_user_by_username(db, username)
    product_ids = list_jjim_product_ids(db, user.id) if user else []
    id_set = set(str(pid) for pid in product_ids)
    
    # processed_clothing_data에서 찜한 상품 찾기
    jjim_products = [p for p in processed_clothing_data if p.get('상품코드') in id_set]
    
    return templates.TemplateResponse("jjim/jjim.html", {"request": request, "jjim_products": jjim_products})


@router.post("/delete", response_class=JSONResponse, dependencies=[Depends(login_required)])
async def delete_selected_jjim(request: Request, db: Session = Depends(get_db), product_ids: str = Form("")):
    username = request.session.get("user_name")
    user = get_user_by_username(db, username)
    if not user:
        return {"success": False, "message": "User not found"}
    
    ids_to_delete = [pid.strip() for pid in product_ids.split(',') if pid.strip()]
    if not ids_to_delete:
        return {"success": False, "message": "No product IDs provided"}

    deleted_count = remove_jjim_bulk(db, user.id, ids_to_delete)
    return {"success": True, "deleted_count": deleted_count}


@router.get("/compare", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def compare_jjim_products(request: Request, ids: Optional[List[str]] = Query(None)): # Changed to Optional and default to None
    sorted_products = []
    if ids: # Only process if IDs are provided
        # 중복 제거 및 순서 유지를 위해 dict.fromkeys 사용
        unique_ids = list(dict.fromkeys(ids))
        id_set = set(unique_ids)

        # processed_clothing_data에서 선택된 상품들의 정보 가져오기
        # 순서는 unique_ids 리스트를 따름
        products_to_compare = [p for p in processed_clothing_data if p.get('상품코드') in id_set]
        
        # id_set 순서가 아닌 unique_ids의 순서를 따르도록 정렬
        products_map = {p.get('상품코드'): p for p in products_to_compare}
        sorted_products = [products_map[pid] for pid in unique_ids if pid in products_map]

    print(f"DEBUG: Products being sent to compare.html: {sorted_products}") # Added debug print
    return templates.TemplateResponse("jjim/compare.html", {
        "request": request, 
        "products": sorted_products # Will be empty if no IDs were provided
    })
