"""External adapters verified with deterministic transports and fail-closed mocks."""

import asyncio
import json

import httpx
import pytest

from app.data.blob import BlobSnapshots, SnapshotConflict
from app.reporting.gemini import CLOSINGS, MODEL, compose, fact_bundle, validate_assembly


def approved_payload():
    return {
        "paragraphs": [
            {
                "section": "executive_summary",
                "opening": "O1",
                "fact_ids": ["DISTRICT", "F03-M01"],
                "closing": "C1",
            }
        ]
    }


def test_ai_unsupported_claims_and_entities_are_rejected(svc):
    facts = fact_bundle(svc.snapshot(), svc.planner(), {})
    assert "IND-03" not in facts and "IND-04" not in facts
    payload = approved_payload()
    sections = validate_assembly(payload, facts)
    assert "Amoxicillin 500 mg" in sections["executive_summary"][0]["text"]
    payload["paragraphs"][0]["opening"] = "999 patients at Unknown Hospital were harmed."
    with pytest.raises(ValueError):
        validate_assembly(payload, facts)
    payload = approved_payload()
    payload["paragraphs"][0]["fact_ids"] = ["UNKNOWN"]
    with pytest.raises(ValueError):
        validate_assembly(payload, facts)
    payload = approved_payload()
    payload["paragraphs"][0]["quantity"] = 999
    with pytest.raises(ValueError):
        validate_assembly(payload, facts)


def test_gemini_request_response_cache_and_prompt_minimisation(svc, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-only")
    calls = []

    def handler(request):
        calls.append(request)
        sent = json.loads(request.content)
        assert sent["model"] == MODEL and sent["store"] is False
        paragraphs = sent["response_format"]["schema"]["properties"]["paragraphs"]
        assert paragraphs["items"]["properties"]["opening"]["enum"] == ["O1", "O2", "O3", "O4"]
        assert "enum" not in paragraphs["items"]["properties"]["fact_ids"]["items"]
        assert request.headers["x-goog-api-key"] == "fake-test-only"
        assert "management secret" not in request.content.decode()
        return httpx.Response(
            200,
            json={
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": json.dumps(approved_payload())}],
                    }
                ]
            },
        )

    args = (
        svc.snapshot(),
        svc.planner(),
        {"narrative_mode": "gemini", "management_note": "management secret"},
        svc.store,
    )
    first = asyncio.run(compose(*args, transport=httpx.MockTransport(handler)))
    assert first["mode"] == "gemini"
    second = asyncio.run(compose(*args, transport=httpx.MockTransport(handler)))
    assert second["fact_hash"] == first["fact_hash"] and len(calls) == 1
    assert "structured_input" not in second
    assert svc.store.ai_calls_today() == 1


def test_verified_free_tier_fallback_is_bounded_and_validated(svc, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-only")
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/interactions"):
            return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
        assert request.url.path.endswith("/gemini-3.5-flash-lite:generateContent")
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(approved_payload())}]}}]}
        )

    result = asyncio.run(
        compose(
            svc.snapshot(),
            svc.planner(),
            {"narrative_mode": "gemini"},
            svc.store,
            transport=httpx.MockTransport(handler),
        )
    )
    assert result["mode"] == "gemini" and len(calls) == 2 and svc.store.ai_calls_today() == 2


@pytest.mark.parametrize("failure", ["quota", "timeout", "unsupported", "bad_json", "oversized"])
def test_gemini_fallbacks(svc, monkeypatch, failure):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-only")

    def handler(request):
        if failure == "quota":
            return httpx.Response(429, json={"error": "quota"})
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout")
        if failure == "oversized":
            return httpx.Response(200, content=b"x" * 50000)
        if failure == "bad_json":
            return httpx.Response(200, json={"output_text": "bad json"})
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "paragraphs": [
                            {
                                "section": "risks",
                                "opening": "Invented 999 units",
                                "fact_ids": ["DISTRICT"],
                                "closing": CLOSINGS[0],
                            }
                        ]
                    }
                )
            },
        )

    result = asyncio.run(
        compose(
            svc.snapshot(),
            svc.planner(),
            {"narrative_mode": "gemini"},
            svc.store,
            transport=httpx.MockTransport(handler),
        )
    )
    assert result["mode"] == "deterministic" and result["sections"] == {}
    assert any(e["event"] == "ai.fallback" for e in svc.store.events())


def test_no_key_non_synthetic_quota_and_model_guards(svc, monkeypatch):
    snapshot, planner = svc.snapshot(), svc.planner()
    request = {"narrative_mode": "gemini"}
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert asyncio.run(compose(snapshot, planner, request, svc.store))["mode"] == "deterministic"
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-only")
    snapshot["context"]["synthetic"] = False
    assert "synthetic" in asyncio.run(compose(snapshot, planner, request, svc.store))["reason"]
    snapshot["context"]["synthetic"] = True
    monkeypatch.setenv("GEMINI_MODEL", "unverified-paid-model")
    assert "verified" in asyncio.run(compose(snapshot, planner, request, svc.store))["reason"]
    monkeypatch.setenv("GEMINI_MODEL", MODEL)
    for n in range(10):
        svc.store.audit("ai.requested", str(n))
    assert "10 daily" in asyncio.run(compose(snapshot, planner, request, svc.store))["reason"]


def test_blob_origin_reads_and_atomic_writes(monkeypatch):
    monkeypatch.setenv("BLOB_STORE_ID", "store_teststore")
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "fake-oidc")
    captured = []

    def handler(request):
        captured.append(request)
        if request.method == "GET":
            assert request.url.params["cache"] == "0"
            return httpx.Response(200, content=b"SQLite format 3\x00test", headers={"etag": "v1"})
        assert request.headers["x-if-match"] == "v1" and request.headers["x-allow-overwrite"] == "1"
        return httpx.Response(200, json={"etag": "v2"})

    store = BlobSnapshots(httpx.MockTransport(handler))
    content, etag = asyncio.run(store.read("workspaces/test.sqlite"))
    asyncio.run(store.write("workspaces/test.sqlite", content, etag))
    assert len(captured) == 2 and captured[0].headers["authorization"] == "Bearer fake-oidc"


def test_blob_conflict_and_missing_snapshot(monkeypatch):
    monkeypatch.delenv("BLOB_STORE_ID", raising=False)
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_teststore_fake")
    store = BlobSnapshots(httpx.MockTransport(lambda r: httpx.Response(404)))
    assert asyncio.run(store.read("workspace.sqlite")) == (None, None)
    store = BlobSnapshots(httpx.MockTransport(lambda r: httpx.Response(412)))
    with pytest.raises(SnapshotConflict):
        asyncio.run(store.write("workspace.sqlite", b"data", "old"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN")
    with pytest.raises(ValueError):
        BlobSnapshots()


def test_hosted_workspace_survives_requests_and_isolated(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main

    snapshots = {}

    class MemorySnapshots:
        async def read(self, path):
            return snapshots.get(path, (None, None))

        async def write(self, path, content, etag):
            current = snapshots.get(path, (None, None))
            if current[1] != etag:
                raise SnapshotConflict("stale")
            snapshots[path] = (content, str(int(etag or 0) + 1))

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(main, "BlobSnapshots", MemorySnapshots)
    with (
        TestClient(main.app, base_url="https://testserver") as a,
        TestClient(main.app, base_url="https://testserver") as b,
    ):
        first = a.get("/api/risk/summary").json()
        rid = first["planner"]["recommendations"][0]["recommendation_id"]
        request = {
            "decision": "accepted",
            "note": "Validated expiry and donor safety.",
            "reviewer": "Test reviewer",
            "expected_version": 1,
            "acknowledged": True,
        }
        assert a.post("/api/redistribution/" + rid + "/review", json=request).status_code == 200
        assert (
            a.get("/api/redistribution/recommendations").json()["recommendations"][0]["status"] == "accepted"
        )
        other = b.get("/api/redistribution/recommendations").json()
        assert other["recommendations"][0]["status"] == "pending"
        assert len(snapshots) == 2
