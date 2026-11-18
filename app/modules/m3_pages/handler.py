from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web import page
from .service import demo, check_volumes

router = APIRouter()
ROWS = [{"key":"2026-11-01|01A","status":"缺页","value":"004"},{"key":"2026-11-01|01B","status":"完整","value":"004"},{"key":"2026-11-03|01","status":"重页","value":"003"}]

@router.get("/pages", response_class=HTMLResponse)
def view(request: Request):
    return page(request, "m3.html", "页码序列", "/api/pages/check", ROWS)

@router.post("/api/pages/check")
def execute():
    return demo()

@router.post("/api/pages/check-volumes")
def check(payload: dict | None = None):
    return check_volumes(payload)
