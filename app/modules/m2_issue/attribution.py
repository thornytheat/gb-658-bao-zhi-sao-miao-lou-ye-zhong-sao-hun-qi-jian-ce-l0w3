"""清单采信归属：期版修订改变采信口径。

旧版号一旦登记修订，新到扫描件若仍打旧版号，不得并入旧账（否则两卷各缺一页
也会被并账验成一本齐卷），按 SUPERSEDED_EDITION 隔离并保留证据，要求改打分卷版号。
"""
from app.store import get_revision


def _business_key(row: dict) -> str:
    return "|".join((str(row["issue"]), str(row["edition"]), str(row["page"])))


def attribute_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    accepted, quarantined = [], []
    for index, row in enumerate(rows, start=1):
        revision = get_revision(str(row["issue"]), str(row["edition"]))
        if revision is not None:
            quarantined.append({
                "business_key": _business_key(row),
                "line_no": row.get("line_no", index),
                "reason_code": "SUPERSEDED_EDITION",
                "raw_value": row["edition"],
                "revision_id": revision["revision_id"],
                "current_editions": [volume["edition"] for volume in revision["volumes"]],
                "raw": row,
            })
        else:
            accepted.append(row)
    return accepted, quarantined
