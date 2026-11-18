import json
import sqlite3

from app.config import DATABASE_PATH
from app.errors import DomainError
from app.reasons import REASONS


def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)

def init_db():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, input_sha256 TEXT NOT NULL, accepted INTEGER NOT NULL, quarantined INTEGER NOT NULL)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS edition_archives ("
            "issue TEXT NOT NULL, edition TEXT NOT NULL, expected_pages INTEGER NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'archive', PRIMARY KEY (issue, edition))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS edition_revisions ("
            "revision_id TEXT PRIMARY KEY, issue TEXT NOT NULL, old_edition TEXT NOT NULL, "
            "volumes_json TEXT NOT NULL, signature TEXT NOT NULL, UNIQUE (issue, old_edition))"
        )

def record_run(manifest: dict) -> bool:
    init_db()
    with connect() as db:
        before = db.total_changes
        db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?)", (manifest["run_id"], manifest["input_sha256"], manifest["accepted"], manifest["quarantined"]))
        return db.total_changes > before

def run_count() -> int:
    init_db()
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

def archive_edition(issue: str, edition: str, expected_pages: int, status: str = "archive") -> bool:
    """登记当年归档。已存在则原样保留，返回是否新建。"""
    init_db()
    with connect() as db:
        before = db.total_changes
        db.execute(
            "INSERT OR IGNORE INTO edition_archives (issue, edition, expected_pages, status) VALUES (?, ?, ?, ?)",
            (issue, edition, expected_pages, status),
        )
        return db.total_changes > before

def register_revision(record: dict) -> dict:
    """单事务登记期版修订。

    - (issue, old_edition) 已有同内容修订：幂等重试，不重复登记；
    - 已有不同内容修订：抛 REVISION_CONFLICT，事务回滚，旧归档保持不动；
    - 首次登记：写入修订并补登两个分卷归档（status=revised），旧版归档行不修改。
    """
    init_db()
    with connect() as db:
        existing = db.execute(
            "SELECT revision_id, signature FROM edition_revisions WHERE issue = ? AND old_edition = ?",
            (record["issue"], record["old_edition"]),
        ).fetchone()
        if existing is not None:
            if existing[1] != record["signature"]:
                raise DomainError("REVISION_CONFLICT", REASONS["REVISION_CONFLICT"])
            return {"revision_id": existing[0], "created": False, "conflict": False}
        volumes_json = json.dumps(record["volumes"], ensure_ascii=False, sort_keys=True)
        db.execute(
            "INSERT INTO edition_revisions (revision_id, issue, old_edition, volumes_json, signature) VALUES (?, ?, ?, ?, ?)",
            (record["revision_id"], record["issue"], record["old_edition"], volumes_json, record["signature"]),
        )
        for volume in record["volumes"]:
            db.execute(
                "INSERT OR IGNORE INTO edition_archives (issue, edition, expected_pages, status) VALUES (?, ?, ?, 'revised')",
                (record["issue"], volume["edition"], volume["expected_pages"]),
            )
        return {"revision_id": record["revision_id"], "created": True, "conflict": False}

def get_archive(issue: str, edition: str) -> dict | None:
    init_db()
    with connect() as db:
        row = db.execute(
            "SELECT issue, edition, expected_pages, status FROM edition_archives WHERE issue = ? AND edition = ?",
            (issue, edition),
        ).fetchone()
    if row is None:
        return None
    return {"issue": row[0], "edition": row[1], "expected_pages": row[2], "status": row[3]}

def get_revision(issue: str, old_edition: str) -> dict | None:
    init_db()
    with connect() as db:
        row = db.execute(
            "SELECT revision_id, issue, old_edition, volumes_json, signature FROM edition_revisions WHERE issue = ? AND old_edition = ?",
            (issue, old_edition),
        ).fetchone()
    if row is None:
        return None
    return {
        "revision_id": row[0],
        "issue": row[1],
        "old_edition": row[2],
        "volumes": json.loads(row[3]),
        "signature": row[4],
    }

def list_revisions(issue: str) -> list[dict]:
    init_db()
    with connect() as db:
        rows = db.execute(
            "SELECT revision_id, issue, old_edition, volumes_json, signature FROM edition_revisions WHERE issue = ? ORDER BY old_edition",
            (issue,),
        ).fetchall()
    return [
        {"revision_id": r[0], "issue": r[1], "old_edition": r[2], "volumes": json.loads(r[3]), "signature": r[4]}
        for r in rows
    ]
