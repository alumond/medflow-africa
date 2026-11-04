"""Cited operational answers from approved analysis; no arbitrary data or clinical advice."""

import json

from app.core.config import ROOT
from app.models.predict import FEATURES, load_model
from app.reporting.gemini import compose
from app.reporting.report import escalation


async def answer(svc, request: dict) -> dict:
    """Resolve supported questions to structured evidence and optional grounded framing."""
    snapshot = svc.snapshot(request["window"])
    planner = svc.planner(request["window"])
    question = request["question"].lower()
    sources, findings, paragraphs = [], [], []
    if any(term in question for term in ("patient", "prescribe", "dosage", "diagnose", "treatment")):
        return {
            "mode": "bounded",
            "title": "This analysis supports operational supply decisions.",
            "paragraphs": [
                "It cannot diagnose patients, select treatment or prescribe doses. Ask about stock-out evidence, model factors, feasible transfers or management escalation."
            ],
            "sources": [
                {
                    "id": "POL-SCOPE",
                    "label": "Responsible AI specification · §4 · Prohibited uses",
                    "type": "policy",
                }
            ],
        }
    eligible = snapshot["pairs"]
    if request.get("finding_id"):
        eligible = [p for p in eligible if p["finding_id"] == request["finding_id"]]
    if any(term in question for term in ("malaria", "antimalarial")):
        eligible = [p for p in eligible if p["category"] == "antimalarial"]
    matched = [
        p
        for p in eligible
        if p["facility"].lower() in question
        or p["facility_id"].lower() in question
        or p["finding_id"].lower() in question
    ]
    medicine_matches = [p for p in eligible if p["medicine"].lower() in question]
    if medicine_matches:
        eligible = medicine_matches
    if matched:
        eligible = [p for p in eligible if p["facility_id"] in {x["facility_id"] for x in matched}]
    draft_request = {
        "window": request["window"],
        "prepared_by": "District supply team",
        "narrative_mode": "gemini" if request["use_gemini"] else "deterministic",
    }
    if "escalat" in question:
        result = escalation(snapshot, planner, draft_request)
        paragraphs = [result["subject"], result["body"]]
        title = "An escalation draft for human review."
        findings = [p for p in eligible if p["risk"] == "high"][:6]
    elif "draft" in question or "brief" in question:
        findings = [p for p in eligible if p["risk"] == "high"][:6]
        title = "The district medicine-supply brief."
        paragraphs.append(
            f"{len(findings)} priority stock positions need review in the {request['window']}-day horizon. Validate the usable balances, confirm overdue deliveries and review the feasible transfer options."
        )
        for p in findings:
            paragraphs.append(
                f"{p['facility']} / {p['medicine']}: {p['stock']:,} units; {p['cover']:.1f} days of cover against {p['safety_days']} days required ({p['cover'] / p['safety_days'] * 100:.1f}% achievement). Open supply is {p['delivery_delay']} days overdue. [{p['finding_id']}]"
            )
        paragraphs.append(
            f"{len(planner['recommendations'])} transfer proposals pass the configured safety checks. The district pharmacist should validate the proposals; the logistics lead should confirm delivery dates. Record owners and deadlines before any external approval."
        )
    elif any(term in question for term in ("transfer", "redistribut", "donor", "safety", "comply")):
        title = "Transfer options that pass the configured safety rules."
        for r in [
            r
            for r in planner["recommendations"]
            if not request.get("recommendation_id") or r["recommendation_id"] == request["recommendation_id"]
        ][:8]:
            paragraphs.append(
                f"{r['medicine']}: {r['quantity']:,} proposed units from {r['donor']} to {r['recipient']}. Recipient cover {r['recipient_before']:.1f} → {r['recipient_after']:.1f} days; donor cover after {r['donor_after']:.1f} days against {r['safety_days']} required. Review status: {r['status']}. [{r['recommendation_id']}]"
            )
            sources.append(
                {
                    "id": r["recommendation_id"],
                    "label": r["medicine"] + " · " + r["recipient"],
                    "type": "recommendation",
                }
            )
        paragraphs.append(
            "These are reviewable proposals. They do not authorise stock movement. Donor stock is reserved across the entire plan; expiry, pack and evidence gates remain mandatory."
        )
        sources.append(
            {
                "id": "POL-REDISTRIBUTION",
                "label": "Data and Model Specification · §13 · Redistribution constraints",
                "type": "policy",
            }
        )
    elif any(term in question for term in ("reporting gaps", "evidence quality", "reporting corrections")):
        title = "Reporting corrections that unlock supply decisions."
        quality = snapshot["quality"]
        paragraphs.append(
            f"{quality['received_reports']} of {quality['expected_reports']} expected weekly reports are valid ({quality['completeness']:.1%}); target 95%. {quality['rejected_count']} rows are quarantined. {quality['blocked_pairs']} pairs remain ineligible for redistribution."
        )
        for facility in quality["facilities"]:
            if facility["blocked_pairs"]:
                paragraphs.append(
                    f"{facility['facility']}: {facility['completeness']:.1%} reporting completeness; {facility['blocked_pairs']} pairs withheld. Reconcile missing source registers and rejected balances before reviewing a transfer."
                )
        findings = [p for p in eligible if p["quality"] in ("limited", "blocked")][:6]
        sources.append(
            {
                "id": "POL-QUALITY",
                "label": "Data and Model Specification · §5 · Evidence quality gates",
                "type": "policy",
            }
        )
    elif any(term in question for term in ("why", "factor", "explain", "evidence")):
        findings = [p for p in eligible if p["risk"] == "high"][:2] or eligible[:1]
        title = "The evidence behind this risk signal."
        for p in findings:
            probability = (
                f"{p['probability']:.1%} model-estimated stock-out probability"
                if p["probability"] is not None
                else "ML probability unavailable"
            )
            paragraphs.append(
                f"{p['facility']} / {p['medicine']}: {probability}; {p['stock']:,} usable units; {p['cover']:.1f} days of cover against {p['safety_days']} required. Evidence quality: {p['quality']}. [{p['finding_id']}]"
            )
            paragraphs.extend(f["text"] + " [" + p["finding_id"] + "]" for f in p["factors"][:4])
            paragraphs.extend(
                f"Model factor: {f['feature'].replace('_', ' ')} {f['direction']}; additive contribution {f['contribution']:+.3f} in log-odds. This is an association, not a causal claim. [{p['finding_id']}]"
                for f in p.get("prediction_factors", [])[:3]
            )
    else:
        findings = sorted(
            [p for p in eligible if p["risk"] in ("high", "medium")], key=lambda p: -(p["probability"] or 0)
        )[:6]
        title = "The medicine–facility pairs to review first."
        for p in findings:
            probability = f"{p['probability']:.1%}" if p["probability"] is not None else "unavailable"
            paragraphs.append(
                f"{p['facility']} / {p['medicine']}: {p['stock']:,} units; {p['cover']:.1f} days versus {p['safety_days']}-day safety target ({p['cover'] / p['safety_days'] * 100:.1f}% achievement). Predicted {request['window']}-day risk: {probability}. Evidence: {p['quality']}. [{p['finding_id']}]"
            )
    for p in findings:
        sources.append(
            {"id": p["finding_id"], "label": p["facility"] + " / " + p["medicine"], "type": "finding"}
        )
    if not paragraphs:
        paragraphs = [
            "No assessable matching risk or eligible transfer was found. Inspect the unassessed queue; missing evidence does not establish adequate stock."
        ]
    draft_request["focus"] = (
        "quality"
        if "reporting corrections" in title.lower()
        else "transfers"
        if "transfer options" in title.lower()
        else "risk"
    )
    narrative = await compose(
        snapshot,
        planner,
        {**draft_request, "selected_findings": [p["finding_id"] for p in findings] if findings else None},
        svc.store,
    )
    if narrative["mode"] == "gemini":
        paragraphs += [p["text"] for p in narrative["sections"].get("recommendations", [])]
    svc.store.audit(
        "copilot.answered",
        snapshot["context"]["import_id"],
        {"source_count": len(sources), "mode": narrative["mode"]},
    )
    return {
        "title": title,
        "paragraphs": paragraphs,
        "sources": sources,
        "mode": narrative["mode"],
        "model": narrative["model"],
        "status_note": narrative["reason"],
        "context": snapshot["context"],
    }


def monitoring(svc, window: int) -> dict:
    """Join synthetic holdout evidence, current feature shifts and live review feedback."""
    snapshot, planner = svc.snapshot(window), svc.planner(window)
    path = ROOT / "model_artifacts/evaluation.json"
    evaluation = json.loads(path.read_text()) if path.exists() else {}
    model = load_model()
    reference = model.get("training_distribution", {}) if model else {}
    drift = []
    for feature in FEATURES:
        if feature == "window":
            continue
        key = {
            "lead_time": "lead_time_days",
            "completeness": "reporting_completeness",
            "trend": "consumption_trend",
            "previous_stockout_days": "previous_stockout_days",
        }.get(feature, feature)
        observed = [p.get(key) for p in snapshot["pairs"] if p.get(key) is not None]
        baseline = reference.get(feature)
        if baseline and observed:
            current = sum(observed) / len(observed)
            score = (
                abs(current - baseline["mean"]) / baseline["std"]
                if baseline["std"] > 0
                else (0 if current == baseline["mean"] else None)
            )
            drift.append(
                {
                    "feature": feature,
                    "current_mean": round(current, 3),
                    "training_mean": round(baseline["mean"], 3),
                    "standardised_shift": round(score, 3) if score is not None else None,
                    "flagged": score is None or score > 2,
                    "n": len(observed),
                }
            )
    feedback = {
        status: sum(r["status"] == status for r in planner["recommendations"])
        for status in ("pending", "accepted", "edited", "rejected")
    }
    reviewed = feedback["accepted"] + feedback["edited"] + feedback["rejected"]
    return {
        "context": snapshot["context"],
        "evaluation": evaluation,
        "drift": drift,
        "feedback": {
            **feedback,
            "reviewed": reviewed,
            "total": len(planner["recommendations"]),
            "review_rate": reviewed / len(planner["recommendations"]) if planner["recommendations"] else None,
        },
        "outcome_note": "False alerts, missed stock-outs and calibration below are measured on the synthetic time holdout. Current-window outcome labels are not yet available. Acceptance is not evidence of model correctness.",
        "drift_note": "Absolute mean shift divided by training standard deviation; investigation flag above 2. Constant training features that change are flagged. This is a simple monitoring trigger, not a validated drift test.",
    }
