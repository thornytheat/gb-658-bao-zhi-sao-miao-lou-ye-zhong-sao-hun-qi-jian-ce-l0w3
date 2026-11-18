from .rules import normalize_issue, normalize_edition, normalize_page
from .catalog import business_key
from .revisions import build_revision
from .lookup import lookup_edition
from .attribution import attribute_rows
from app import store
from app.errors import DomainError
from app.reasons import REASONS

# 纯规则层抛出的 ValueError 码到领域错误码的映射（无专属原因码时按格式错误处理）
_VALUE_ERROR_CODES = {
    "BAD_VOLUME": "BAD_VOLUME",
    "BAD_VOLUMES": "BAD_FORMAT",
    "BAD_COUNT": "BAD_FORMAT",
    "DUPLICATE_VOLUME": "DUPLICATE_KEY",
    "BAD_EDITION": "BAD_FORMAT",
    "BAD_PAGE": "BAD_FORMAT",
}


def _to_domain_error(exc: ValueError) -> DomainError:
    code = str(exc)
    domain_code = _VALUE_ERROR_CODES.get(code, "BAD_FORMAT")
    return DomainError(domain_code, REASONS.get(domain_code, code))


def _missing_field_error(exc: KeyError) -> DomainError:
    return DomainError("EMPTY_VALUE", f"{REASONS['EMPTY_VALUE']}: {exc.args[0]}")


def run(payload: dict | None = None) -> dict:
    payload = payload or {"issue": "2026/11/01", "edition": "1", "page": "001"}
    item = {"issue": normalize_issue(payload["issue"]), "edition": normalize_edition(payload["edition"]), "page": normalize_page(payload["page"])}
    item["business_key"] = business_key(item)
    return item

def revise(payload: dict) -> dict:
    """登记期版修订：旧版号拆两卷。失败抛异常并回滚，重试幂等不重复登记。"""
    try:
        record = build_revision(payload)
    except ValueError as exc:
        raise _to_domain_error(exc) from exc
    except KeyError as exc:
        raise _missing_field_error(exc) from exc
    result = store.register_revision(record)
    return {**record, **result}

def revise_issue(payload: dict | None = None) -> dict:
    payload = payload or {
        "issue": "2026-11-01",
        "old_edition": "01",
        "volumes": [
            {"edition": "01A", "expected_pages": 4},
            {"edition": "01B", "expected_pages": 4},
        ],
    }
    return revise(payload)

def query_edition(payload: dict | None = None) -> dict:
    payload = payload or {"issue": "2026-11-01", "edition": "01"}
    try:
        issue, edition = normalize_issue(payload["issue"]), normalize_edition(payload["edition"])
    except ValueError as exc:
        raise _to_domain_error(exc) from exc
    except KeyError as exc:
        raise _missing_field_error(exc) from exc
    return lookup_edition(issue, edition)

def attribute(payload: dict | None = None) -> dict:
    payload = payload or {"rows": []}
    rows = payload.get("rows", [])
    accepted, quarantined = attribute_rows(rows)
    return {"input": len(rows), "accepted": accepted, "quarantined": quarantined,
            "accepted_count": len(accepted), "quarantined_count": len(quarantined)}

def demo():
    return run()
