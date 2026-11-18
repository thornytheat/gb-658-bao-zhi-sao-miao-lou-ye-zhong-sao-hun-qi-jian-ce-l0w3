from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web import page
from .service import demo, revise_issue, query_edition, attribute

router = APIRouter()
ROWS = [{"key":"2026-11-01|01","status":"已归档（待修订）","value":"8"},{"key":"2026-11-01|01A","status":"分卷一","value":"4"},{"key":"2026-11-01|01B","status":"分卷二","value":"4"}]

@router.get("/issues", response_class=HTMLResponse)
def view(request: Request):
    return page(request, "m2.html", "期版契约", "/api/issues/normalize", ROWS)

@router.post("/api/issues/normalize")
def execute():
    return demo()

@router.post("/api/issues/revise")
def revise(payload: dict | None = None):
    return revise_issue(payload)

@router.post("/api/issues/lookup")
def lookup(payload: dict | None = None):
    return query_edition(payload)

@router.post("/api/issues/attribute")
def attribute_scans(payload: dict | None = None):
    return attribute(payload)
