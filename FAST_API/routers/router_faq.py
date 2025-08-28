from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dependencies import login_required

from sqlalchemy.orm import Session
from db import get_db
from crud.faq_crud import get_all_faqs

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def faq(request: Request, db: Session = Depends(get_db)):
    faq_data_from_db = get_all_faqs(db)
    return templates.TemplateResponse("faq/faq.html", {"request": request, "faq_data": faq_data_from_db})