from datetime import datetime
import re

def normalize_issue(value: str) -> str:
    value = value.strip().replace("/", "-")
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()

def normalize_edition(value: str) -> str:
    token = value.strip().upper()
    if token.startswith("S"):
        return token
    if not token.isdigit() or int(token) < 1:
        raise ValueError("BAD_EDITION")
    return f"{int(token):02d}"

def normalize_volume_edition(value: str, base_edition: str) -> str:
    """期版修订拆分出的卷号：必须在旧版号基础上带字母后缀，如 01 -> 01A/01B。

    纯数字（01、1）与增刊号（S1）都不是卷号，避免与标准版/增刊的版次空间冲突。
    裸后缀（A/B）自动补全为旧版号前缀。
    """
    token = value.strip().upper()
    base = normalize_edition(base_edition)
    if not re.fullmatch(r"[A-Z0-9]+", token):
        raise ValueError("BAD_VOLUME")
    if token.isalpha():
        token = f"{base}{token}"
    if token.isdigit() or token.startswith("S") or not re.search(r"[A-Z]$", token):
        raise ValueError("BAD_VOLUME")
    if not token.startswith(base):
        raise ValueError("BAD_VOLUME")
    return token

def normalize_page(value: str) -> str:
    token = value.strip()
    if not re.fullmatch(r"\d+", token) or int(token) < 1:
        raise ValueError("BAD_PAGE")
    return f"{int(token):03d}"

def expected_pages(count: int) -> list[str]:
    if count < 1:
        raise ValueError("BAD_COUNT")
    return [f"{n:03d}" for n in range(1, count + 1)]

