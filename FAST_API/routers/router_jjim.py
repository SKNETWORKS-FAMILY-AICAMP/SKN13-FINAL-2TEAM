from fastapi import APIRouter, Request, HTTPException, Depends
from dependencies import login_required
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from database import get_all_products, get_random_products
import urllib.parse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(login_required)])
async def jjim_list(request: Request):
    # For the demo, get 12 random products to act as the user's wishlist
    jjim_products = get_random_products(12)
    return templates.TemplateResponse("jjim/jjim.html", {"request": request, "jjim_products": jjim_products})