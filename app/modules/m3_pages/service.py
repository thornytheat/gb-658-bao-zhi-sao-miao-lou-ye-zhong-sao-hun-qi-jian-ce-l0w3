from .sequence import inspect_pages, select_versions, inspect_by_volume
from .reconcile import page_accounts
from app.store import list_revisions

def run(pages: list[dict] | None = None) -> dict:
    pages = pages or [{"page": "001", "version": 1, "clarity": 80}, {"page": "002", "version": 1, "clarity": 70}, {"page": "002", "version": 2, "clarity": 90}, {"page": "004", "version": 1, "clarity": 88}]
    selected = select_versions(pages)
    status = inspect_pages([x["page"] for x in selected], 4)
    return {**status, **page_accounts(len(pages), selected, status)}

def check_volumes(payload: dict | None = None) -> dict:
    """分卷验页：计划取自已登记修订，结论随清单采信归属逐卷更新。"""
    payload = payload or _demo_payload()
    pages = payload.get("pages", [])
    issue = payload.get("issue")
    if not issue:
        from app.errors import DomainError
        from app.reasons import REASONS
        raise DomainError("EMPTY_VALUE", f"{REASONS['EMPTY_VALUE']}: issue")
    plans = payload.get("plans") or _plans_for_issue(issue)
    report = inspect_by_volume(pages, plans)
    report["issue"] = issue
    return report

def _plans_for_issue(issue: str) -> list[dict]:
    plans = []
    for revision in list_revisions(issue):
        for volume in revision["volumes"]:
            plans.append({"edition": volume["edition"], "expected_pages": volume["expected_pages"]})
    return plans

def _demo_payload() -> dict:
    return {
        "issue": "2026-11-01",
        "pages": [
            {"edition": "01A", "page": "001", "version": 1, "clarity": 80},
            {"edition": "01A", "page": "002", "version": 1, "clarity": 70},
            {"edition": "01A", "page": "003", "version": 1, "clarity": 75},
            {"edition": "01B", "page": "001", "version": 1, "clarity": 80},
            {"edition": "01B", "page": "002", "version": 1, "clarity": 70},
            {"edition": "01B", "page": "003", "version": 1, "clarity": 75},
            {"edition": "01B", "page": "004", "version": 1, "clarity": 88},
        ],
    }

def demo():
    return run()
