"""Safety boundaries, evidence gates, validation and longitudinal model isolation."""

import hashlib
import json
from datetime import timedelta

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from app.core.config import POLICY, ROOT
from app.core.schemas import Inventory, Order, ReviewRequest
from app.data.generate import END, generate
from app.data.programme import programme
from app.data.validation import parse_csv, validate_bundle
from app.models.predict import FEATURES, SCHEMA_HASH, load_model, predict
from app.reporting.report import SECTIONS, build_report, email_file, escalation, validate_narrative
from app.services.analysis import days_cover, risk_band
from app.services.redistribution import feasible_quantity, validate_review
from scripts.train_model import samples, time_split


def test_generator_is_reproducible_and_complete():
    a, b = generate(), generate()
    assert a == b and len(a["facilities"]) == len(a["medicines"]) == 10
    dates = sorted({r["reporting_date"] for r in a["inventory"]})
    assert len(dates) == 60 and dates[-1] == END.isoformat()


@pytest.mark.parametrize("stock,adc,expected", [(100, 10, 10), (0, 10, 0), (100, 0, None), (0, 0, None)])
def test_cover_handles_zero(stock, adc, expected):
    assert days_cover(stock, adc) == expected


@pytest.mark.parametrize(
    "prob,band",
    [(0, "low"), (0.2999, "low"), (0.3, "medium"), (0.5999, "medium"), (0.6, "high"), (1, "high")],
)
def test_exact_risk_boundaries(prob, band):
    assert risk_band(prob) == band


@pytest.mark.parametrize(
    "changes",
    [
        {"closing_balance": -1},
        {"closing_balance": 9999999},
        {"stockout_days": 8},
        {"quantity_near_expiry": 9999999},
        {"expiry_date": "2020-01-01"},
        {"report_submitted_on_time": "maybe"},
    ],
)
def test_inventory_rejects_invalid_values(changes):
    row = generate()["inventory"][0]
    with pytest.raises(ValidationError):
        Inventory.model_validate({**row, **changes})


def test_valid_balance():
    row = generate()["inventory"][0]
    parsed = Inventory.model_validate(row)
    assert (
        parsed.closing_balance
        == parsed.opening_balance + parsed.quantity_received - parsed.quantity_dispensed + parsed.adjustments
    )


def test_duplicate_all_copies_quarantined():
    bundle = generate()
    bundle["inventory"].append(bundle["inventory"][0].copy())
    result = validate_bundle(bundle, END)
    duplicates = [r for r in result["rejected"] if r["rule"] == "DUPLICATE"]
    assert len(duplicates) == 2
    assert not any(r["record_id"] == bundle["inventory"][0]["record_id"] for r in result["data"]["inventory"])


@pytest.mark.parametrize(
    "field,value,rule",
    [
        ("facility_id", "unknown", "REFERENCE"),
        ("medicine_id", "unknown", "REFERENCE"),
        ("reporting_date", "2027-01-01", "FUTURE_DATE"),
    ],
)
def test_reference_and_cutoff(field, value, rule):
    bundle = generate()
    bundle["inventory"][0][field] = value
    if field == "reporting_date":
        bundle["inventory"][0]["expiry_date"] = "2028-01-01"
    assert any(r["rule"] == rule for r in validate_bundle(bundle, END)["rejected"])


@pytest.mark.parametrize(
    "content,match",
    [
        (b"patient_id,foo\n1,2", "prohibited"),
        (b"facility_id\nF1", "Missing required"),
        (b"x,x\n1,2", "Duplicate"),
        (b"\xff,foo", "UTF-8"),
    ],
)
def test_structural_csv_rejection(content, match):
    with pytest.raises(ValueError, match=match):
        parse_csv(content, "facilities")


def test_parse_csv_real_data():
    rows = parse_csv((ROOT / "data/demo/orders.csv").read_bytes(), "orders")
    assert any(r["actual_delivery_date"] is None for r in rows)
    assert len(rows) == 100


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity_ordered": 0},
        {"expected_delivery_date": "2000-01-01"},
        {"order_status": "fulfilled", "actual_delivery_date": None},
        {"order_status": "pending", "quantity_delivered": 2},
        {"order_status": "partial", "quantity_delivered": 0},
    ],
)
def test_inconsistent_orders(changes):
    row = next(r for r in generate()["orders"] if r["order_status"] == "fulfilled")
    with pytest.raises(ValidationError):
        Order.model_validate({**row, **changes})


def test_scenario_risk_quality_and_order_delay(svc):
    a = svc.snapshot(14)
    pairs = {p["finding_id"]: p for p in a["pairs"]}
    assert pairs["F03-M01"]["risk"] == "high" and pairs["F03-M01"]["delivery_delay"] == 9
    assert pairs["F03-M01"]["consumption_trend"] > 0.15
    assert pairs["F10-M01"]["risk"] == "not_assessed"
    assert pairs["F05-M06"]["quality"] == "blocked"
    assert pairs["F07-M10"]["cover"] is None
    assert len(a["quality"]["rejected"]) == 1
    b = {p["finding_id"]: p for p in svc.snapshot(30)["pairs"]}
    assert pairs["F03-M07"]["baseline_at_risk"] is False
    assert b["F03-M07"]["baseline_at_risk"] is True
    assert a["quality"]["timeliness"] < a["quality"]["completeness"]


def test_missing_weeks_are_not_zero_consumption(svc):
    p = next(p for p in svc.snapshot()["pairs"] if p["finding_id"] == "F10-M01")
    assert p["observed_days"] < 28 and p["adc"] > 0
    assert any(h["stock"] is None for h in p["history"])


def test_all_feasible_proposals_and_shared_reservations(svc):
    result = svc.planner(30)
    snapshot = svc.snapshot(30)
    pairs = {p["finding_id"]: p for p in snapshot["pairs"]}
    total = {}
    for r in result["recommendations"]:
        assert r["quantity"] > 0 and r["quantity"] % r["pack_size"] == 0
        assert r["donor_after"] >= r["safety_days"] - 0.005
        assert r["recipient_after"] <= r["shelf_life_days"] - POLICY["transport_buffer_days"] + 0.005
        donor = r["donor_id"] + "-" + r["medicine_id"]
        total[donor] = total.get(donor, 0) + r["quantity"]
    for donor, quantity in total.items():
        p = pairs[donor]
        assert p["stock"] - quantity >= p["adc"] * p["safety_days"]
    assert any(r["near_expiry"] for r in result["recommendations"])
    assert all(r["recipient_id"] != "F10" for r in result["recommendations"])


def transfer_pair():
    base = {
        "facility_id": "A",
        "medicine_id": "M01",
        "quality": "strong",
        "adc": 10,
        "expiry_date": (END + timedelta(days=90)).isoformat(),
        "minimum_shelf_life_days": 7,
        "stock": 1000,
        "safety_days": 21,
        "pack_size": 100,
    }
    return base, {**base, "facility_id": "B", "stock": 50}


@pytest.mark.parametrize(
    "changes",
    [
        {"stock": 210},
        {"stock": 0},
        {"adc": 0},
        {"expiry_date": None},
        {"expiry_date": (END + timedelta(days=2)).isoformat()},
        {"quality": "blocked"},
        {"quality": "limited"},
        {"facility_id": "B"},
        {"medicine_id": "different"},
    ],
)
def test_donor_hard_constraints(changes):
    donor, recipient = transfer_pair()
    assert feasible_quantity({**donor, **changes}, recipient, END) == 0


@pytest.mark.parametrize(
    "changes", [{"adc": 0}, {"quality": "limited"}, {"expiry_date": None}, {"stock": None}, {"stock": 400}]
)
def test_recipient_hard_constraints(changes):
    donor, recipient = transfer_pair()
    assert feasible_quantity(donor, {**recipient, **changes}, END) == 0


@given(
    stock=st.integers(0, 100000),
    adc=st.integers(1, 500),
    pack=st.integers(1, 500),
    reserved=st.integers(0, 100000),
)
def test_transfer_invariants(stock, adc, pack, reserved):
    donor, recipient = transfer_pair()
    donor.update(stock=stock, adc=adc, pack_size=pack)
    q = feasible_quantity(donor, recipient, END, reserved)
    assert q >= 0 and q % pack == 0
    if q:
        assert stock - reserved - q >= adc * donor["safety_days"]


def test_review_history_stale_lock_and_validation(svc):
    r = svc.planner()["recommendations"][0]
    request = {
        "decision": "accepted",
        "reviewer": "Test pharmacist",
        "note": "Verified balances and expiry.",
        "expected_version": 1,
        "acknowledged": True,
    }
    first = svc.review(r["recommendation_id"], request)
    assert first["version"] == 2
    with pytest.raises(RuntimeError):
        svc.review(r["recommendation_id"], request)
    edited = {
        **request,
        "decision": "edited",
        "expected_version": 2,
        "quantity": r["quantity"] - r["pack_size"],
    }
    if edited["quantity"] > 0:
        saved = svc.review(r["recommendation_id"], edited)
        assert saved["version"] == 3
        assert svc.planner()["recommendations"][0]["quantity"] == r["quantity"]
    rejected = {
        **request,
        "decision": "rejected",
        "expected_version": svc.store.reviews()[r["recommendation_id"]]["version"],
    }
    assert svc.review(r["recommendation_id"], rejected)["decision"] == "rejected"
    with pytest.raises(LookupError):
        svc.review("unknown", request)


@pytest.mark.parametrize(
    "changes",
    [
        {"decision": "edited", "quantity": 1000000},
        {"decision": "edited", "quantity": 1},
        {"decision": "edited", "quantity": 0},
        {"decision": "accepted", "quantity": 100},
        {"acknowledged": False},
    ],
)
def test_unsafe_edits_are_rejected(svc, changes):
    r = svc.planner()["recommendations"][0]
    request = {"decision": "accepted", "acknowledged": True, **changes}
    with pytest.raises(ValueError):
        validate_review(r, request)


def test_notes_and_acknowledgement_required():
    with pytest.raises(ValidationError):
        ReviewRequest(decision="accepted", reviewer="test", note="", expected_version=1, acknowledged=True)
    with pytest.raises(ValidationError):
        ReviewRequest(
            decision="accepted", reviewer="test", note="valid note", expected_version=1, acknowledged=False
        )


def test_import_idempotence_and_audit_integrity(svc):
    a = svc.load_demo()
    b = svc.load_demo()
    assert a["import_id"] == b["import_id"] and b["idempotent"]
    import sqlite3

    with svc.store.connect() as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("DELETE FROM audit")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE audit SET event='changed'")


def test_complete_report_and_separate_specific_email(svc):
    snapshot, planner = svc.snapshot(), svc.planner()
    html = build_report(
        snapshot, planner, {"management_note": "<script>bad()</script>", "prepared_by": "M&E lead"}
    )
    positions = [html.index(f"<h2>{section}</h2>") for section in SECTIONS]
    assert positions == sorted(positions) and html.count("<section id=") == 13
    assert "<script>bad" not in html and "&lt;script&gt;" in html
    assert "US$128,750" in html and "% achievement" in html
    assert "Stock officers trained" not in html and "physical stock verification" not in html
    assert "training places" not in escalation(snapshot, planner, {})["body"]
    draft = escalation(snapshot, planner, {"prepared_by": "M&E lead"})
    assert draft["warranted"] and "Amoxicillin 500 mg" in draft["body"] and "9 days" in draft["body"]
    assert "District pharmacist" in draft["body"] and "2026-11-06" in draft["subject"]
    assert b"X-Unsent: 1" in email_file(draft)
    assert validate_narrative([{"fact_id": "F1", "text": "12 units"}], {"F1": "12 units"})
    assert not validate_narrative([{"fact_id": "F1", "text": "999 units"}], {"F1": "12 units"})
    assert not validate_narrative([{"fact_id": "UNKNOWN", "text": "New Hospital"}], {"F1": "12 units"})


def test_programme_ledger_reconciles(svc):
    p = programme(svc.snapshot(), svc.planner())
    assert sum(b["allocated"] for b in p["budget"]) == 185000
    assert sum(b["spent"] for b in p["budget"]) == 128750
    assert all(b["spent"] + b["committed"] <= b["allocated"] for b in p["budget"])
    assert len([a for a in p["activities"] if a["status"] == "completed"]) == 5


def test_model_schema_and_tampering(tmp_path):
    model = {
        "version": "test",
        "approved": True,
        "schema_hash": SCHEMA_HASH,
        "median": [0] * len(FEATURES),
        "mean": [0] * len(FEATURES),
        "scale": [1] * len(FEATURES),
        "coefficient": [0] * len(FEATURES),
        "intercept": 0,
    }
    p = tmp_path / "model.json"
    p.write_text(json.dumps(model))
    p.with_suffix(".sha256").write_text(hashlib.sha256(p.read_bytes()).hexdigest())
    assert predict([1] * len(FEATURES), p)["probability"] == 0.5
    assert predict([None] * len(FEATURES), p)["probability"] == 0.5
    assert predict([float("nan")] * len(FEATURES), p) is None
    assert predict([1], p) is None
    p.write_text("{}")
    assert load_model(p) is None
    assert load_model(tmp_path / "missing.json") is None


def test_model_time_split_has_no_label_leakage():
    rows = samples()
    split = time_split(rows)
    assert max(r["label_end"] for r in split["train"]) < min(r["date"] for r in split["validation"])
    assert max(r["label_end"] for r in split["validation"]) < min(r["date"] for r in split["test"])
    assert all(r["feature_max_date"] <= r["date"] and r["label_end"] <= END.isoformat() for r in rows)
    artifact = json.loads((ROOT / "model_artifacts/evaluation.json").read_text())
    assert artifact["test"]["sample_count"] > 0 and set(artifact["subgroups"]) >= {
        "location_type",
        "facility_type",
        "medicine_category",
    }
    assert artifact["test"]["calibration"]["observed_rate"]
