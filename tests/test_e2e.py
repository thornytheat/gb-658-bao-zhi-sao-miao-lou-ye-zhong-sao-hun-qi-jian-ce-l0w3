from fastapi.testclient import TestClient
from app.main import app


def test_all_module_pages_accessible():
    client = TestClient(app)
    for path in ("/intake", "/issues", "/pages", "/rescans", "/mixed", "/batches"):
        response = client.get(path)
        assert response.status_code == 200 and "panel" in response.text

def test_full_sample_flow_has_business_results():
    client = TestClient(app)
    endpoints = ("/api/scans/import", "/api/issues/normalize", "/api/pages/check", "/api/rescans/evaluate", "/api/mixed/evaluate", "/api/reconcile")
    results = [client.post(path).json() for path in endpoints]
    assert results[0]["accepted"] == 2 and results[2]["missing"] == [3] and results[4]["decision"] == "MIXED_ISSUE"

def test_export_matches_page_evidence():
    client = TestClient(app)
    response = client.get("/api/export/evidence.csv")
    assert response.status_code == 200 and "MISSING_PAGE" in response.text


class TestIssueRevisionFlow:
    """旧版号拆两卷：修订登记 -> 旧号查卷 -> 采信归属 -> 分卷验页 -> 失败回滚与幂等。"""

    def test_full_revision_flow_over_http(self, tmp_path, monkeypatch):
        import app.config as config
        import app.store as store
        db_path = tmp_path / "e2e.sqlite3"
        monkeypatch.setattr(config, "DATABASE_PATH", db_path)
        monkeypatch.setattr(store, "DATABASE_PATH", db_path)
        client = TestClient(app)

        # 当年按旧号归档（一本 8 页）
        store.archive_edition("2026-11-01", "01", 8)

        # 登记修订：旧号 01 拆成 01A/01B 两卷
        revision = {
            "issue": "2026-11-01",
            "old_edition": "01",
            "volumes": [
                {"edition": "01A", "expected_pages": 4},
                {"edition": "01B", "expected_pages": 4},
            ],
        }
        first = client.post("/api/issues/revise", json=revision)
        assert first.status_code == 200 and first.json()["created"] is True

        # 重试不重复登记
        retry = client.post("/api/issues/revise", json=revision)
        assert retry.status_code == 200 and retry.json()["created"] is False

        # 冲突修订被拒（422），旧归档保持不变
        conflict = dict(revision, volumes=[
            {"edition": "01A", "expected_pages": 6},
            {"edition": "01B", "expected_pages": 2},
        ])
        blocked = client.post("/api/issues/revise", json=conflict)
        assert blocked.status_code == 422
        assert blocked.json()["detail"]["code"] == "REVISION_CONFLICT"

        # 旧号查卷：当年归档与更正后两卷都在
        lookup = client.post("/api/issues/lookup", json={"issue": "2026-11-01", "edition": "01"})
        body = lookup.json()
        assert body["revised"] is True
        assert body["archive"]["expected_pages"] == 8
        assert body["current_editions"] == ["01A", "01B"]

        # 旧号扫描件隔离，分卷扫描件采纳
        attribution = client.post("/api/issues/attribute", json={"rows": [
            {"issue": "2026-11-01", "edition": "01", "page": "001", "line_no": 2},
            {"issue": "2026-11-01", "edition": "01A", "page": "001", "line_no": 3},
            {"issue": "2026-11-01", "edition": "01B", "page": "001", "line_no": 4},
        ]}).json()
        assert attribution["quarantined_count"] == 1
        assert attribution["quarantined"][0]["reason_code"] == "SUPERSEDED_EDITION"

        # 分卷验页：两卷各只有 001，均不完整，不会被并账验成齐卷
        check = client.post("/api/pages/check-volumes", json={
            "issue": "2026-11-01",
            "pages": attribution["accepted"],
        }).json()
        editions = {volume["edition"]: volume for volume in check["volumes"]}
        assert editions["01A"]["missing"] == [2, 3, 4]
        assert editions["01B"]["missing"] == [2, 3, 4]
        assert check["complete"] is False

    def test_bad_volume_code_rejected_over_http(self, tmp_path, monkeypatch):
        import app.config as config
        import app.store as store
        db_path = tmp_path / "e2e.sqlite3"
        monkeypatch.setattr(config, "DATABASE_PATH", db_path)
        monkeypatch.setattr(store, "DATABASE_PATH", db_path)
        client = TestClient(app)
        response = client.post("/api/issues/revise", json={
            "issue": "2026-11-01",
            "old_edition": "01",
            "volumes": [
                {"edition": "01", "expected_pages": 4},
                {"edition": "01B", "expected_pages": 4},
            ],
        })
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "BAD_VOLUME"

