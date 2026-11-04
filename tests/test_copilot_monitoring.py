"""Expanded AI workflow: three horizons, explanation, citations and feedback monitoring."""

import hashlib
import json

import pytest

from app.models.predict import load_model, predict


@pytest.mark.parametrize(
    "question",
    [
        "Which facilities are most likely to run out of malaria medicines?",
        "Why is Oke Rural Clinic classified as high risk?",
        "Which transfer options comply with the safety-stock policy?",
        "Draft an escalation note for the district manager.",
        "What dosage should this patient receive?",
        "Why does Gidan Rural Clinic have a reporting gap?",
    ],
)
def test_cited_copilot_and_scope(client, question):
    response = client.post("/api/copilot/ask", json={"question": question, "window": 14, "use_gemini": False})
    assert response.status_code == 200
    result = response.json()
    assert result["paragraphs"] and result["sources"]
    if "patient" in question:
        assert result["mode"] == "bounded"
    elif "malaria" in question:
        assert any("Artemether" in p for p in result["paragraphs"])
        assert all(s["type"] == "finding" for s in result["sources"])
    elif "transfer" in question:
        assert any(s["type"] == "policy" for s in result["sources"])


def test_prediction_and_contributions_all_horizons(client):
    for horizon in (7, 14, 30):
        response = client.get(f"/api/risk/summary?window={horizon}")
        assert response.status_code == 200
        pairs = response.json()["pairs"]
        predicted = [p for p in pairs if p["probability"] is not None]
        assert predicted and all(0 <= p["probability"] <= 1 for p in predicted)
        assert all(p["prediction_factors"] and p["explanation_method"] for p in predicted)
        assert all(
            p["risk"] == "high"
            for p in pairs
            if p["baseline_at_risk"] and p["quality"] in ("strong", "acceptable") and p["cover"] is not None
        )


def test_monitoring_is_explicit_about_holdout_and_feedback(client):
    before = client.get("/api/monitoring/summary?window=7").json()
    assert before["drift"] and before["evaluation"]["validation_models"]["logistic"]
    assert before["evaluation"]["validation_models"]["gradient_boosting"]
    assert "synthetic" in before["outcome_note"] and before["feedback"]["reviewed"] == 0
    summary = client.get("/api/risk/summary?window=7").json()
    proposal = summary["planner"]["recommendations"][0]
    review = {
        "decision": "rejected",
        "reviewer": "Pharmacist",
        "note": "Transport route needs confirmation.",
        "expected_version": 1,
        "acknowledged": True,
    }
    assert (
        client.post(
            f"/api/redistribution/{proposal['recommendation_id']}/review?window=7", json=review
        ).status_code
        == 200
    )
    after = client.get("/api/monitoring/summary?window=7").json()
    assert after["feedback"]["reviewed"] == 1 and after["feedback"]["rejected"] == 1


def test_active_model_json_inference_matches_training_library():
    # Predicting a current pair requires no sklearn, numpy or unsafe deserialisation.
    model = load_model()
    assert model["approved"]
    result = predict([6, 250, 40, 0.2, 21, 1, 0, 0, 14])
    assert result and result["version"] == model["version"] and result["factors"]


def test_contextual_explanations_respect_the_selected_record(client):
    answer = client.post(
        "/api/copilot/ask",
        json={"question": "Explain this risk", "finding_id": "F03-M01", "window": 14, "use_gemini": False},
    ).json()
    assert all(source["id"] == "F03-M01" for source in answer["sources"])
    proposal = client.get("/api/redistribution/recommendations").json()["recommendations"][0]
    answer = client.post(
        "/api/copilot/ask",
        json={
            "question": "Explain safe transfer options",
            "recommendation_id": proposal["recommendation_id"],
            "window": 14,
            "use_gemini": False,
        },
    ).json()
    assert len([source for source in answer["sources"] if source["type"] == "recommendation"]) == 1
    answer = client.post(
        "/api/copilot/ask",
        json={
            "question": "Summarise reporting gaps and evidence quality issues",
            "window": 14,
            "use_gemini": False,
        },
    ).json()
    assert any("Gidan" in p for p in answer["paragraphs"])
    assert any(source["id"] == "POL-QUALITY" for source in answer["sources"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_hash", "wrong"),
        ("approved", False),
        ("scale", [0] * 9),
        ("mean", [1]),
        ("intercept", float("inf")),
        ("learning_rate", 0),
        ("trees", []),
    ],
)
def test_corrupt_model_metadata_is_rejected(tmp_path, field, value):
    from app.core.config import ROOT

    source = json.loads((ROOT / "model_artifacts/active.json").read_text())
    source[field] = value
    path = tmp_path / "model.json"
    path.write_text(json.dumps(source))
    path.with_suffix(".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    assert load_model(path) is None


def test_corrupt_tree_cycle_is_rejected(tmp_path):
    from app.core.config import ROOT

    source = json.loads((ROOT / "model_artifacts/active.json").read_text())
    source["trees"][0]["left"][0] = 0
    path = tmp_path / "model.json"
    path.write_text(json.dumps(source))
    path.with_suffix(".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    assert load_model(path) is None
