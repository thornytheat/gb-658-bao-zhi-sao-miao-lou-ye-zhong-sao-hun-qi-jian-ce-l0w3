import pytest

import app.config as config
import app.store as store
from app.modules.m2_issue.service import revise, attribute
from app.modules.m3_pages.sequence import inspect_pages, inspect_by_volume
from app.modules.m3_pages.service import check_volumes


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(config, "DATABASE_PATH", path)
    monkeypatch.setattr(store, "DATABASE_PATH", path)
    store.init_db()
    return path


PLANS = [
    {"edition": "01A", "expected_pages": 4},
    {"edition": "01B", "expected_pages": 4},
]

# 两卷都缺第 4 页：朴素并账（共用旧号）会把 001-003 看成一套，误判为只缺一页的单卷。
PAGES_MISSING_PER_VOLUME = [
    {"edition": "01A", "page": "001", "version": 1, "clarity": 80},
    {"edition": "01A", "page": "002", "version": 1, "clarity": 70},
    {"edition": "01A", "page": "003", "version": 1, "clarity": 75},
    {"edition": "01B", "page": "001", "version": 1, "clarity": 80},
    {"edition": "01B", "page": "002", "version": 1, "clarity": 70},
    {"edition": "01B", "page": "003", "version": 1, "clarity": 75},
]


def test_pooled_old_key_masks_missing_page():
    # 反例：沿用旧号把两卷并成一本验，001-003 各出现两次 -> 只报缺 004，看似单卷缺页
    pooled = [row["page"] for row in PAGES_MISSING_PER_VOLUME]
    status = inspect_pages(pooled, 4)
    assert status["missing"] == [4] and status["duplicates"] == [1, 2, 3]


def test_per_volume_check_flags_missing_in_each_volume():
    report = inspect_by_volume(PAGES_MISSING_PER_VOLUME, PLANS)
    by_edition = {volume["edition"]: volume for volume in report["volumes"]}
    assert by_edition["01A"]["missing"] == [4]
    assert by_edition["01B"]["missing"] == [4]
    assert report["complete"] is False


def test_complete_when_each_volume_full():
    pages = PAGES_MISSING_PER_VOLUME + [
        {"edition": "01A", "page": "004", "version": 1, "clarity": 90},
        {"edition": "01B", "page": "004", "version": 1, "clarity": 90},
    ]
    report = inspect_by_volume(pages, PLANS)
    assert report["complete"] is True
    assert all(volume["missing"] == [] for volume in report["volumes"])


def test_unexpected_edition_reported():
    pages = [{"edition": "01C", "page": "001", "version": 1, "clarity": 80}]
    report = inspect_by_volume(pages, PLANS)
    assert report["unexpected_editions"] == ["01C"]
    assert report["complete"] is False


def test_version_selection_kept_per_volume():
    pages = [
        {"edition": "01A", "page": "001", "version": 1, "clarity": 99},
        {"edition": "01A", "page": "001", "version": 2, "clarity": 50},
    ]
    report = inspect_by_volume(pages, PLANS)
    volume_a = next(v for v in report["volumes"] if v["edition"] == "01A")
    assert volume_a["selected"][0]["version"] == 2
    assert volume_a["superseded"] == 1


def test_check_volumes_uses_registered_revision_plans(temp_db):
    revise({
        "issue": "2026-11-01",
        "old_edition": "01",
        "volumes": [
            {"edition": "01A", "expected_pages": 4},
            {"edition": "01B", "expected_pages": 4},
        ],
    })
    report = check_volumes({"issue": "2026-11-01", "pages": PAGES_MISSING_PER_VOLUME})
    assert {v["edition"] for v in report["volumes"]} == {"01A", "01B"}
    assert report["complete"] is False


def test_conclusion_updates_with_attribution(temp_db):
    """期版修订改变采信归属后，旧号扫描件被隔离，分卷验页结论随归属更新。"""
    revise({
        "issue": "2026-11-01",
        "old_edition": "01",
        "volumes": [
            {"edition": "01A", "expected_pages": 4},
            {"edition": "01B", "expected_pages": 4},
        ],
    })
    incoming = [
        {"issue": "2026-11-01", "edition": "01", "page": "001", "line_no": 2},
        {"issue": "2026-11-01", "edition": "01", "page": "002", "line_no": 3},
        {"issue": "2026-11-01", "edition": "01A", "page": "001", "version": 1, "clarity": 80, "line_no": 4},
        {"issue": "2026-11-01", "edition": "01B", "page": "001", "version": 1, "clarity": 80, "line_no": 5},
    ]
    result = attribute({"rows": incoming})
    assert result["quarantined_count"] == 2
    report = check_volumes({"issue": "2026-11-01", "pages": result["accepted"]})
    by_edition = {volume["edition"]: volume for volume in report["volumes"]}
    # 旧号两页不并入分卷账，两卷都只剩 001，缺 002-004
    assert by_edition["01A"]["missing"] == [2, 3, 4]
    assert by_edition["01B"]["missing"] == [2, 3, 4]
    assert report["complete"] is False
