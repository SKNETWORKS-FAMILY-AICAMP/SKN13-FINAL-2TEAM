from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/chatbot-page")
def chatbot_page(request: Request):
    return templates.TemplateResponse("chatbot.html", {"request": request, "title": "Chatbot"})
