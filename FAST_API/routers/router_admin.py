from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dependencies import admin_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse, dependencies=[Depends(admin_required)])
async def admin_dashboard(request: Request):
    """관리자 대시보드 페이지"""
    try:
        return templates.TemplateResponse("admin/admin_dashboard.html", {"request": request})
    except Exception as e:
        print(f"관리자 대시보드 템플릿 오류: {e}")
        raise HTTPException(status_code=500, detail="템플릿 로드 오류")

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(admin_required)])
async def admin_root(request: Request):
    """관리자 루트 페이지 - 대시보드로 리다이렉트"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin/dashboard")

@router.get("/test", response_class=HTMLResponse)
async def admin_test(request: Request):
    """관리자 테스트 페이지 (의존성 없음)"""
    return templates.TemplateResponse("admin/admin_dashboard.html", {"request": request})

@router.get("/debug", response_class=HTMLResponse)
async def admin_debug(request: Request):
    """관리자 디버그 페이지"""
    return HTMLResponse(content="<h1>관리자 라우터가 작동합니다!</h1>")
