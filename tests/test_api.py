"""Critical browser/API/data workflows, import separation and review concurrency."""

from app.core.config import ROOT


def test_overview_horizons_and_filter_contract(client):
    for window in (14, 30):
        response = client.get(f"/api/risk/summary?window={window}")
        assert response.status_code == 200
        assert sum(response.json()["counts"].values()) == 100
        assert response.headers["X-Correlation-ID"]
    assert client.get("/api/risk/summary?window=20").status_code == 422
    assert client.get("/api/risk/summary?window=bad").status_code == 422
    pairs = client.get("/api/risk/details?facility=F03&medicine=M01&risk=high&quality=strong").json()["pairs"]
    assert len(pairs) == 1 and pairs[0]["finding_id"] == "F03-M01"
    assert client.get("/api/risk/details?facility=unknown").json()["pairs"] == []


def test_review_valid_unsafe_missing_and_stale(client):
    r = client.get("/api/redistribution/recommendations?window=14").json()["recommendations"][0]
    url = f"/api/redistribution/{r['recommendation_id']}/review?window=14"
    base = {
        "decision": "accepted",
        "reviewer": "District pharmacist",
        "note": "Expiry and balances checked.",
        "expected_version": 1,
        "acknowledged": True,
    }
    assert client.post(url, json={**base, "note": ""}).status_code == 422
    assert client.post(url, json={**base, "acknowledged": False}).status_code == 422
    assert (
        client.post(
            url, json={**base, "decision": "edited", "quantity": r["max_quantity"] + r["pack_size"]}
        ).status_code
        == 422
    )
    response = client.post(url, json=base)
    assert response.status_code == 200 and response.json()["version"] == 2
    assert client.post(url, json=base).status_code == 409
    refreshed = client.get("/api/redistribution/recommendations").json()["recommendations"][0]
    assert refreshed["status"] == "accepted" and refreshed["quantity"] == r["quantity"]
    assert client.post("/api/redistribution/missing/review", json=base).status_code == 404
    events = client.get("/api/audit/events?limit=200").json()["events"]
    assert any(e["event"] == "recommendation.accepted" for e in events)
    assert all("note" not in e["metadata"] for e in events)


def test_report_draft_and_html_email_exports(client):
    draft = {
        "window": 14,
        "narrative_mode": "gemini",
        "prepared_by": "M&E lead",
        "management_note": "<img src=x onerror=alert(1)>",
        "actions": [
            {
                "finding_id": "F03-M01",
                "owner": "District pharmacist",
                "action": "Validate balances and review the proposal.",
                "due_date": "2026-11-06",
                "status": "open",
            }
        ],
    }
    assert client.put("/api/reports/draft", json=draft).status_code == 200
    assert client.get("/api/reports/draft").json()["actions"][0]["owner"] == "District pharmacist"
    response = client.post("/api/reports/action-report?download=true", json=draft)
    assert response.status_code == 200 and response.text.count("<section id=") == 13
    assert "<img src=x" not in response.text and "District medicine-supply brief" in response.text
    assert "attachment" in response.headers["Content-Disposition"]
    email = client.post("/api/reports/escalation", json=draft)
    assert email.status_code == 200 and email.json()["warranted"]
    assert "Variance" in email.json()["body"].title()
    assert (
        client.post("/api/reports/escalation?download=true", json=draft)
        .headers["content-type"]
        .startswith("message/rfc822")
    )
    assert client.get("/api/reports/action-report?window=30").status_code == 200
    assert client.get("/api/ai/status").json()["configured"] is False
    assert client.post("/api/ai/narrative", json=draft).json()["mode"] == "deterministic"


def upload_files(inventory=None):
    return {
        entity: (
            entity + ".csv",
            inventory
            if entity == "inventory" and inventory is not None
            else (ROOT / f"data/demo/{entity}.csv").read_bytes(),
            "text/csv",
        )
        for entity in ("facilities", "medicines", "inventory", "orders")
    }


def test_import_validation_provenance_idempotence(client):
    response = client.post(
        "/api/data/import",
        files=upload_files(),
        data={"cutoff": "2026-11-01", "anonymised_confirmed": "true"},
    )
    assert response.status_code == 200
    imported = response.json()
    assert imported["approved"] and len(imported["rejected"]) == 1
    assert all("checksum" in s for s in imported["sources"])
    assert client.get("/api/data/imports/" + imported["import_id"]).json()["accepted"] == imported["accepted"]
    assert (
        client.post(
            "/api/data/import",
            files=upload_files(),
            data={"cutoff": "2026-11-01", "anonymised_confirmed": "true"},
        ).json()["import_id"]
        == imported["import_id"]
    )
    assert client.get("/api/data/quality").json()["rejected_count"] == 1
    assert "BALANCE" in client.get("/api/data/rejections.csv").text
    assert client.get("/api/data/imports/unknown").status_code == 404


def test_prohibited_and_incomplete_uploads_preserve_active_dataset(client):
    before = client.get("/api/risk/summary").json()["context"]["import_id"]
    for data in (
        {"cutoff": "2026-11-01"},
        {"cutoff": "2026-11-01", "anonymised_confirmed": "true", "schema_version": "999"},
    ):
        assert client.post("/api/data/import", files=upload_files(), data=data).status_code == 422
    bad = client.post(
        "/api/data/import",
        files=upload_files(b"patient_id,record_id\nsecret,1"),
        data={"cutoff": "2026-11-01", "anonymised_confirmed": "true"},
    )
    assert bad.status_code == 422 and "prohibited" in bad.text
    assert "secret" not in bad.text
    assert client.get("/api/risk/summary").json()["context"]["import_id"] == before


def test_demo_downloads_and_quality_api(client):
    assert client.post("/api/data/demo").status_code == 200
    assert client.get("/api/data/demo/facilities.csv").status_code == 200
    assert client.get("/api/data/demo/unknown.csv").status_code == 404
    q = client.get("/api/data/quality").json()
    assert q["accepted"] + q["rejected_count"] == q["total"]
    assert client.get("/api/model/evaluation").json()["synthetic"] is True
    assert client.get("/api/audit/events?limit=201").status_code == 422
    assert client.get("/api/health").json()["llm_enabled"] is False
    assert client.get("/").status_code == 200
    assert client.get("/assets/garamond.ttf").status_code == 200
