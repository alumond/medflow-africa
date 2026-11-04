"""Deterministic inventory metrics, quality gates and traceable risk evidence."""

import os
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Optional

from app.core.config import POLICY
from app.models.predict import predict


def days_cover(stock: float, adc: float) -> Optional[float]:
    """Zero demand means unknown cover, never infinity."""
    return stock / adc if adc > 0 else None


def risk_band(probability: float) -> str:
    """Map exact probability boundaries using the versioned policy."""
    if probability >= POLICY["high_probability"]:
        return "high"
    return "medium" if probability >= POLICY["medium_probability"] else "low"


def analyze(imported: dict, window: int = 14) -> dict:
    """Build one immutable snapshot from a validated import and explicit horizon."""
    if window not in (7, 14, 30):
        raise ValueError("Forecast window must be 7, 14 or 30 days")
    if not imported["approved"]:
        raise ValueError("Import is blocked by missing reference or inventory data")
    data = imported["data"]
    cutoff = date.fromisoformat(imported["cutoff"])
    groups = defaultdict(list)
    for row in data["inventory"]:
        groups[(row["facility_id"], row["medicine_id"])].append(row)
    orders = defaultdict(list)
    for row in data["orders"]:
        orders[(row["facility_id"], row["medicine_id"])].append(row)
    rejected = imported["rejected"]
    pairs = []
    lookback = cutoff - timedelta(weeks=POLICY["lookback_weeks"] - 1)
    for facility in data["facilities"]:
        if not facility["active"]:
            continue
        for medicine in data["medicines"]:
            if not medicine["active"]:
                continue
            fid, mid = facility["facility_id"], medicine["medicine_id"]
            history = sorted(groups[(fid, mid)], key=lambda x: x["reporting_date"])
            recent = [x for x in history if lookback.isoformat() <= x["reporting_date"] <= cutoff.isoformat()]
            short = [x for x in recent if x["reporting_date"] >= (cutoff - timedelta(weeks=3)).isoformat()]
            current = history[-1] if history else None
            completeness = len(recent) / POLICY["lookback_weeks"]
            adc = sum(x["quantity_dispensed"] for x in short) / (7 * len(short)) if short else 0
            long_adc = sum(x["quantity_dispensed"] for x in recent) / (7 * len(recent)) if recent else 0
            trend = adc / long_adc - 1 if long_adc > 0 else None
            stock = current["closing_balance"] if current else None
            stale_days = (cutoff - date.fromisoformat(current["reporting_date"])).days if current else None
            pair_rejections = [
                r
                for r in rejected
                if r["entity"] == "inventory" and r["facility_id"] == fid and r["medicine_id"] == mid
            ]
            latest_invalid = any(
                r["reporting_date"] >= (current["reporting_date"] if current else "") for r in pair_rejections
            )
            critical = current is None or (stale_days is not None and stale_days > 7) or latest_invalid
            quality = (
                "blocked"
                if critical
                else "limited"
                if completeness < POLICY["quality_minimum"]
                else "strong"
                if completeness >= POLICY["quality_strong"]
                else "acceptable"
            )
            cover = days_cover(stock, adc) if stock is not None else None
            pair_orders = orders[(fid, mid)]
            open_orders = [o for o in pair_orders if o["order_status"] in ("pending", "partial")]
            delay = max(
                [max(0, (cutoff - date.fromisoformat(o["expected_delivery_date"])).days) for o in open_orders]
                or [0]
            )
            fulfilment = (
                sum(o["quantity_delivered"] for o in pair_orders)
                / sum(o["quantity_ordered"] for o in pair_orders)
                if pair_orders
                else None
            )
            factors = []
            if cover is not None:
                factors.append(
                    {
                        "id": "cover",
                        "type": "Calculated",
                        "text": f"{cover:.1f} days of stock cover against a {medicine['safety_stock_days']}-day safety threshold.",
                        "actual": round(cover, 2),
                        "target": medicine["safety_stock_days"],
                    }
                )
            if delay:
                factors.append(
                    {
                        "id": "delay",
                        "type": "Reported",
                        "text": f"An open order is {delay} days overdue at the reporting cut-off.",
                        "actual": delay,
                        "target": 0,
                    }
                )
            if trend is not None and trend > 0.15:
                factors.append(
                    {
                        "id": "surge",
                        "type": "Calculated",
                        "text": f"Recent daily consumption is {trend:.0%} above the 12-week observed average.",
                        "actual": round(trend * 100, 1),
                        "target": 0,
                    }
                )
            if fulfilment is not None and fulfilment < 1:
                factors.append(
                    {
                        "id": "partial",
                        "type": "Reported",
                        "text": f"{fulfilment:.0%} of ordered units delivered; target 100%.",
                        "actual": round(fulfilment * 100, 1),
                        "target": 100,
                    }
                )
            factors.append(
                {
                    "id": "reports",
                    "type": "Calculated",
                    "text": f"{len(recent)} of {POLICY['lookback_weeks']} expected weekly reports received ({completeness:.0%}); target {POLICY['reporting_target']:.0%}.",
                    "actual": round(completeness * 100, 1),
                    "target": POLICY["reporting_target"] * 100,
                }
            )
            causes = []
            if delay:
                causes.append(
                    {
                        "label": "Delayed delivery",
                        "type": "Confirmed",
                        "detail": f"Open order {delay} days overdue",
                    }
                )
            if trend is not None and trend > 0.15:
                causes.append(
                    {
                        "label": "Consumption surge",
                        "type": "Inferred",
                        "detail": "Recent demand exceeds the observed historical average",
                    }
                )
            if any(o["order_status"] == "partial" for o in open_orders):
                causes.append(
                    {
                        "label": "Partially filled order",
                        "type": "Confirmed",
                        "detail": "Source order marked partial",
                    }
                )
            if completeness < POLICY["reporting_target"] or critical:
                causes.append(
                    {
                        "label": "Stock-record discrepancy" if latest_invalid else "Reporting gap",
                        "type": "Confirmed",
                        "detail": "Rejected balance or missing expected reports",
                    }
                )
            near_expiry = current["quantity_near_expiry"] if current else 0
            if near_expiry:
                causes.append(
                    {
                        "label": "Near-expiry overstock",
                        "type": "Inferred",
                        "detail": f"{near_expiry:,} units flagged near expiry",
                    }
                )
            if cover is not None and cover < medicine["safety_stock_days"] and not delay:
                causes.append(
                    {
                        "label": "Insufficient order quantity",
                        "type": "Inferred",
                        "detail": "Usable cover is below the configured safety stock",
                    }
                )
            features = [
                cover,
                stock,
                adc,
                trend,
                facility["lead_time_days"],
                completeness,
                sum(r["stockout_days"] for r in recent),
                near_expiry,
                window,
            ]
            prediction = predict(features) if quality not in ("blocked", "limited") and adc > 0 else None
            baseline = cover < window if cover is not None else None
            if critical or completeness < POLICY["quality_minimum"] or cover is None:
                band = "not_assessed"
            else:
                baseline_band = (
                    "high"
                    if baseline
                    else "medium"
                    if cover < max(window + 7, medicine["safety_stock_days"])
                    else "low"
                )
                band = max(
                    (
                        baseline_band,
                        (
                            "high"
                            if prediction["probability"] >= prediction["high_threshold"]
                            else "medium"
                            if prediction["probability"]
                            >= min(POLICY["medium_probability"], prediction["high_threshold"] / 2)
                            else "low"
                        )
                        if prediction
                        else "low",
                    ),
                    key=lambda b: {"low": 0, "medium": 1, "high": 2}[b],
                )
            warnings = []
            if latest_invalid:
                warnings.append(
                    "Latest inventory evidence was rejected. Earlier stock is shown for context; redistribution is blocked."
                )
            if quality in ("blocked", "limited"):
                warnings.append(
                    f"Recommendations withheld: {completeness:.0%} reporting completeness; minimum {POLICY['quality_minimum']:.0%} and fresh, valid stock required."
                )
            if adc == 0:
                warnings.append(
                    "No observed consumption in the recent window. Stock cover and redistribution are not assessed."
                )
            if current and not current["expiry_date"]:
                warnings.append("Expiry evidence missing; redistribution withheld.")
            pairs.append(
                {
                    "finding_id": fid + "-" + mid,
                    "facility_id": fid,
                    "medicine_id": mid,
                    "facility": facility["facility_name"],
                    "medicine": medicine["medicine_name"],
                    "location_type": facility["location_type"],
                    "facility_type": facility["facility_type"],
                    "category": medicine["category"],
                    "stock": stock,
                    "adc": adc,
                    "observed_days": len(short) * 7,
                    "cover": round(cover, 2) if cover is not None else None,
                    "safety_days": medicine["safety_stock_days"],
                    "reorder_point": round(
                        adc * (facility["lead_time_days"] + medicine["safety_stock_days"])
                    ),
                    "pack_size": medicine["pack_size"],
                    "minimum_shelf_life_days": medicine["minimum_shelf_life_days"],
                    "expiry_date": current["expiry_date"] if current else None,
                    "near_expiry": near_expiry,
                    "consumption_trend": round(trend, 4) if trend is not None else None,
                    "reporting_completeness": round(completeness, 4),
                    "quality": quality,
                    "risk": band,
                    "baseline_at_risk": baseline,
                    "probability": prediction["probability"] if prediction else None,
                    "model": prediction["version"] if prediction else "Deterministic baseline",
                    "prediction_factors": prediction["factors"] if prediction else [],
                    "explanation_method": prediction["explanation_method"] if prediction else None,
                    "operating_threshold": prediction["high_threshold"] if prediction else None,
                    "lead_time_days": facility["lead_time_days"],
                    "previous_stockout_days": sum(r["stockout_days"] for r in recent),
                    "delivery_delay": delay,
                    "fulfilment": fulfilment,
                    "open_order_units": sum(
                        o["quantity_ordered"] - o["quantity_delivered"] for o in open_orders
                    ),
                    "factors": factors[:5],
                    "causes": causes
                    or [
                        {
                            "label": "No identifiable cause",
                            "type": "Inferred",
                            "detail": "No configured bottleneck rule triggered",
                        }
                    ],
                    "warnings": warnings,
                    "last_report": current["reporting_date"] if current else None,
                    "history": [
                        {
                            "date": (cutoff - timedelta(weeks=w)).isoformat(),
                            **next(
                                (
                                    {
                                        "stock": r["closing_balance"],
                                        "dispensed": r["quantity_dispensed"],
                                        "received": r["quantity_received"],
                                        "stockout_days": r["stockout_days"],
                                    }
                                    for r in recent
                                    if r["reporting_date"] == (cutoff - timedelta(weeks=w)).isoformat()
                                ),
                                {"stock": None, "dispensed": None, "received": None, "stockout_days": None},
                            ),
                        }
                        for w in reversed(range(12))
                    ],
                    "latitude": facility["latitude"],
                    "longitude": facility["longitude"],
                }
            )
    pairs.sort(
        key=lambda p: (
            {"high": 0, "medium": 1, "not_assessed": 2, "low": 3}[p["risk"]],
            -(p["probability"] or 0),
            p["cover"] if p["cover"] is not None else 100000,
            p["finding_id"],
        )
    )
    quality_summary = quality_metrics(imported, pairs)
    return {
        "pairs": pairs,
        "quality": quality_summary,
        "context": {
            "district": POLICY["district"],
            "window": window,
            "cutoff": imported["cutoff"],
            "period_start": min(x["reporting_date"] for x in data["inventory"]),
            "import_id": imported["import_id"],
            "data_version": imported["checksum"][:10],
            "config_version": POLICY["version"],
            "schema_version": POLICY["schema_version"],
            "synthetic": imported["synthetic"],
            "created_at": imported["created_at"],
            "model": next(
                (p["model"] for p in pairs if p["probability"] is not None), "Deterministic baseline"
            ),
            "model_note": "Evaluated ML estimate; conservative baseline alert retained"
            if any(p["probability"] is not None for p in pairs)
            else "ML score unavailable or not promoted. Showing the deterministic baseline.",
            "llm_enabled": bool(os.environ.get("GEMINI_API_KEY")),
        },
    }


def quality_metrics(imported: dict, pairs: list[dict]) -> dict:
    """Calculate dimensions using explicit expected-report and source-row denominators."""
    data = imported["data"]
    cutoff = date.fromisoformat(imported["cutoff"])
    start = cutoff - timedelta(weeks=11)
    recent = [r for r in data["inventory"] if r["reporting_date"] >= start.isoformat()]
    expected = len(pairs) * 12
    inventory_rejected = [r for r in imported["rejected"] if r["entity"] == "inventory"]
    inventory_total = len(data["inventory"]) + len(inventory_rejected)
    facilities = []
    for facility in data["facilities"]:
        subset = [p for p in pairs if p["facility_id"] == facility["facility_id"]]
        if not subset:
            continue
        facilities.append(
            {
                "facility_id": facility["facility_id"],
                "facility": facility["facility_name"],
                "location_type": facility["location_type"],
                "completeness": round(mean(p["reporting_completeness"] for p in subset), 4),
                "blocked_pairs": sum(p["quality"] in ("blocked", "limited") for p in subset),
                "quality": "blocked"
                if any(p["quality"] == "blocked" for p in subset)
                else "limited"
                if any(p["quality"] == "limited" for p in subset)
                else "strong",
                "high_risk": sum(p["risk"] == "high" for p in subset),
            }
        )
    return {
        "accepted": imported["accepted"],
        "rejected_count": len(imported["rejected"]),
        "total": imported["total"],
        "completeness": len(recent) / expected if expected else 0,
        "timeliness": sum(r["report_submitted_on_time"] for r in recent) / expected if expected else 0,
        "validity": imported["accepted"] / imported["total"] if imported["total"] else 0,
        "consistency": 1 - sum(r["rule"] == "BALANCE" for r in inventory_rejected) / max(inventory_total, 1),
        "uniqueness": 1
        - sum(r["rule"] == "DUPLICATE" for r in imported["rejected"]) / max(imported["total"], 1),
        "expected_reports": expected,
        "received_reports": len(recent),
        "facilities": facilities,
        "rejected": imported["rejected"],
        "sources": imported["sources"],
        "checksum": imported["checksum"],
        "blocked_pairs": sum(p["quality"] in ("blocked", "limited") for p in pairs),
        "target": POLICY["reporting_target"],
        "import_id": imported["import_id"],
    }
