"""期版修订：同一个旧版号被报社补发增刊目录拆成两卷。

修订登记后：
- 旧版号的当年归档保留不动（archive 状态仍可按旧号查到）；
- 修订指向两个分卷版号，清单采信与验页按分卷归属；
- 同一 (issue, old_edition) 重复提交：内容相同视为重试（幂等），内容冲突拒绝。
"""
from hashlib import sha256
import json

from .rules import normalize_issue, normalize_edition, normalize_volume_edition


def revision_id(issue: str, old_edition: str) -> str:
    """修订的稳定标识：期号 + 旧版号，保证重试命中同一登记，不重复入账。"""
    raw = f"{issue}|{old_edition}".encode("utf-8")
    return f"REV-{sha256(raw).hexdigest()[:12]}"


def build_revision(payload: dict) -> dict:
    """规范化一条修订请求，返回可落库的修订记录（不接触数据库，纯函数）。"""
    issue = normalize_issue(payload["issue"])
    old_edition = normalize_edition(payload["old_edition"])
    volumes_in = payload.get("volumes")
    if not isinstance(volumes_in, list) or len(volumes_in) != 2:
        raise ValueError("BAD_VOLUMES")
    volumes, seen = [], set()
    for item in volumes_in:
        edition = normalize_volume_edition(item["edition"], old_edition)
        count = int(item["expected_pages"])
        if count < 1:
            raise ValueError("BAD_COUNT")
        if edition in seen:
            raise ValueError("DUPLICATE_VOLUME")
        seen.add(edition)
        volumes.append({"edition": edition, "expected_pages": count})
    volumes.sort(key=lambda each: each["edition"])
    record = {
        "revision_id": revision_id(issue, old_edition),
        "issue": issue,
        "old_edition": old_edition,
        "volumes": volumes,
        "signature": _signature(issue, old_edition, volumes),
    }
    return record


def _signature(issue: str, old_edition: str, volumes: list[dict]) -> str:
    body = json.dumps(
        {"issue": issue, "old_edition": old_edition, "volumes": volumes},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(body).hexdigest()[:16]


def volume_editions(revision: dict) -> list[str]:
    return [each["edition"] for each in revision["volumes"]]


def is_same_revision(existing_signature: str, candidate: dict) -> bool:
    return existing_signature == candidate["signature"]
