from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import random

router = APIRouter()
templates = Jinja2Templates(directory="templates")

df = pd.read_csv("products.csv")
df["대표이미지URL"] = "https:" + df["대표이미지URL"]
clothing_data = df.to_dict("records")

@router.get("/", response_class=HTMLResponse)
async def preference(request: Request):
    items = random.sample(clothing_data, 20) if len(clothing_data) > 20 else clothing_data
    return templates.TemplateResponse(
        "preference/preference.html", 
        {"request": request, "recommended_items": items}
    )