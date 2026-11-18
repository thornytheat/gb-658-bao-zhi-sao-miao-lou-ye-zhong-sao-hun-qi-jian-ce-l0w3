import pytest

import app.config as config
import app.store as store
from app.errors import DomainError
from app.modules.m2_issue.revisions import build_revision, revision_id
from app.modules.m2_issue.rules import normalize_volume_edition
from app.modules.m2_issue.service import revise, query_edition, attribute
from app.modules.m2_issue.lookup import lookup_edition


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(config, "DATABASE_PATH", path)
    monkeypatch.setattr(store, "DATABASE_PATH", path)
    store.init_db()
    return path


def revision_payload(issue="2026-11-01", old_edition="01",
                      volumes=None):
    return {
        "issue": issue,
        "old_edition": old_edition,
        "volumes": volumes or [
            {"edition": "01A", "expected_pages": 4},
            {"edition": "01B", "expected_pages": 4},
        ],
    }


def test_normalize_volume_edition_requires_suffix():
    assert normalize_volume_edition("a", "01") == "01A"
    assert normalize_volume_edition("01B", "1") == "01B"
    with pytest.raises(ValueError, match="BAD_VOLUME"):
        normalize_volume_edition("01", "01")
    with pytest.raises(ValueError, match="BAD_VOLUME"):
        normalize_volume_edition("S1", "01")
    with pytest.raises(ValueError, match="BAD_VOLUME"):
        normalize_volume_edition("02A", "01")


def test_build_revision_sorts_volumes_and_signs():
    payload = revision_payload(volumes=[
        {"edition": "01B", "expected_pages": 4},
        {"edition": "01A", "expected_pages": 2},
    ])
    record = build_revision(payload)
    assert [v["edition"] for v in record["volumes"]] == ["01A", "01B"]
    assert record["revision_id"] == revision_id("2026-11-01", "01")


def test_build_revision_requires_exactly_two_volumes():
    payload = revision_payload(volumes=[{"edition": "01A", "expected_pages": 4}])
    with pytest.raises(ValueError, match="BAD_VOLUMES"):
        build_revision(payload)


def test_duplicate_volume_code_rejected():
    payload = revision_payload(volumes=[
        {"edition": "01A", "expected_pages": 4},
        {"edition": "a", "expected_pages": 4},
    ])
    with pytest.raises(ValueError, match="DUPLICATE_VOLUME"):
        build_revision(payload)


def test_register_keeps_old_archive_and_adds_volume_archives(temp_db):
    store.archive_edition("2026-11-01", "01", 8)
    result = revise(revision_payload())
    assert result["created"] is True
    old = store.get_archive("2026-11-01", "01")
    assert old["status"] == "archive" and old["expected_pages"] == 8
    assert store.get_archive("2026-11-01", "01A")["status"] == "revised"
    assert store.get_archive("2026-11-01", "01B")["expected_pages"] == 4


def test_retry_same_revision_is_idempotent(temp_db):
    store.archive_edition("2026-11-01", "01", 8)
    first = revise(revision_payload())
    second = revise(revision_payload())
    assert first["revision_id"] == second["revision_id"]
    assert first["created"] is True and second["created"] is False
    rows = store.connect().execute("SELECT COUNT(*) FROM edition_revisions").fetchone()[0]
    assert rows == 1


def test_conflicting_revision_rejected_and_old_archive_untouched(temp_db):
    store.archive_edition("2026-11-01", "01", 8)
    revise(revision_payload())
    conflict = revision_payload(volumes=[
        {"edition": "01A", "expected_pages": 6},
        {"edition": "01B", "expected_pages": 2},
    ])
    with pytest.raises(DomainError) as exc:
        revise(conflict)
    assert exc.value.code == "REVISION_CONFLICT"
    old = store.get_archive("2026-11-01", "01")
    assert old["status"] == "archive" and old["expected_pages"] == 8
    # 冲突不产生第二条修订，分卷归档仍是首次登记的期望页
    assert store.get_archive("2026-11-01", "01A")["expected_pages"] == 4


def test_lookup_returns_archive_and_corrected_volumes(temp_db):
    store.archive_edition("2026-11-01", "01", 8)
    revise(revision_payload())
    result = lookup_edition("2026-11-01", "01")
    assert result["revised"] is True
    assert result["archive"]["expected_pages"] == 8
    assert result["current_editions"] == ["01A", "01B"]
    assert {v["edition"] for v in result["volumes"]} == {"01A", "01B"}


def test_lookup_unknown_edition_raises(temp_db):
    with pytest.raises(DomainError) as exc:
        query_edition({"issue": "2026-11-01", "edition": "99"})
    assert exc.value.code == "UNKNOWN_REFERENCE"


def test_lookup_without_revision_still_returns_archive(temp_db):
    store.archive_edition("2026-11-02", "02", 6)
    result = query_edition({"issue": "2026-11-02", "edition": "2"})
    assert result["revised"] is False
    assert result["archive"]["edition"] == "02"
    assert result["current_editions"] == ["02"]


def test_attribution_quarantines_old_edition_scans(temp_db):
    revise(revision_payload())
    rows = [
        {"issue": "2026-11-01", "edition": "01", "page": "001", "line_no": 2},
        {"issue": "2026-11-01", "edition": "01A", "page": "001", "line_no": 3},
    ]
    result = attribute({"rows": rows})
    assert result["accepted_count"] == 1 and result["quarantined_count"] == 1
    evidence = result["quarantined"][0]
    assert evidence["reason_code"] == "SUPERSEDED_EDITION"
    assert evidence["raw_value"] == "01"
    assert evidence["current_editions"] == ["01A", "01B"]
    assert result["accepted"][0]["edition"] == "01A"


def test_missing_field_raises_domain_error(temp_db):
    with pytest.raises(DomainError) as exc:
        revise({"issue": "2026-11-01"})
    assert exc.value.code == "EMPTY_VALUE"
    assert store.connect().execute("SELECT COUNT(*) FROM edition_revisions").fetchone()[0] == 0
