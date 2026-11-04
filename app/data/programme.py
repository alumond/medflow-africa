"""Illustrative logistics records alongside calculated inventory and review indicators."""

from datetime import date, timedelta


def programme(snapshot: dict, planner: dict) -> dict:
    """Derive operational indicators and join them to explicitly synthetic programme ledgers."""
    cutoff = date.fromisoformat(snapshot["context"]["cutoff"])
    activities = [
        {
            "id": "ACT-01",
            "name": "Facility baseline and stock mapping",
            "owner": "Supply information lead",
            "planned": 10,
            "actual": 10,
            "unit": "facilities",
            "status": "completed",
            "start": "2026-08-03",
            "due": "2026-08-28",
            "dependency": "None",
        },
        {
            "id": "ACT-03",
            "name": "Validate weekly reporting pipeline",
            "owner": "Data officer",
            "planned": 10,
            "actual": 10,
            "unit": "facilities",
            "status": "completed",
            "start": "2026-08-31",
            "due": "2026-09-18",
            "dependency": "ACT-01",
        },
        {
            "id": "ACT-05",
            "name": "Agree redistribution review protocol",
            "owner": "District supply manager",
            "planned": 1,
            "actual": 1,
            "unit": "protocol",
            "status": "completed",
            "start": "2026-09-07",
            "due": "2026-09-25",
            "dependency": "ACT-03",
        },
        {
            "id": "ACT-06",
            "name": "Complete district supply review",
            "owner": "Logistics lead",
            "planned": 3,
            "actual": 3,
            "unit": "reviews",
            "status": "completed",
            "start": "2026-09-01",
            "due": "2026-10-30",
            "dependency": "ACT-05",
        },
        {
            "id": "ACT-07",
            "name": "Approve data-governance procedures",
            "owner": "Supply information lead",
            "planned": 1,
            "actual": 1,
            "unit": "procedure",
            "status": "completed",
            "start": "2026-08-10",
            "due": "2026-09-04",
            "dependency": "ACT-01",
        },
        {
            "id": "ACT-08",
            "name": "Next district supply decision review",
            "owner": "District supply manager",
            "planned": 1,
            "actual": 0,
            "unit": "review",
            "status": "planned",
            "start": "2026-11-09",
            "due": "2026-11-13",
            "dependency": "ACT-06",
        },
    ]
    budget = [
        {
            "line": "Facility stock-information support",
            "allocated": 48000,
            "spent": 32800,
            "committed": 6200,
            "planned_to_date": 42000,
            "owner": "Supply information lead",
        },
        {
            "line": "Last-mile logistics",
            "allocated": 62000,
            "spent": 51200,
            "committed": 7400,
            "planned_to_date": 49600,
            "owner": "Logistics lead",
        },
        {
            "line": "Stock information systems",
            "allocated": 38000,
            "spent": 26750,
            "committed": 3200,
            "planned_to_date": 30400,
            "owner": "Supply information lead",
        },
        {
            "line": "District coordination",
            "allocated": 25000,
            "spent": 18000,
            "committed": 2100,
            "planned_to_date": 20000,
            "owner": "District supply manager",
        },
        {
            "line": "Contingency",
            "allocated": 12000,
            "spent": 0,
            "committed": 0,
            "planned_to_date": 6000,
            "owner": "Finance manager",
        },
    ]
    assessed = [p for p in snapshot["pairs"] if p["risk"] != "not_assessed"]
    safe = sum(p["cover"] >= p["safety_days"] for p in assessed)
    reviews = sum(r["status"] != "pending" for r in planner["recommendations"])
    indicators = [
        {
            "id": "IND-01",
            "name": "Facility-medicine pairs meeting safety stock",
            "level": "Outcome",
            "actual": round(safe / max(len(assessed), 1) * 100, 1),
            "target": 95,
            "unit": "%",
            "basis": f"{safe} of {len(assessed)} assessable pairs; unassessed pairs excluded and disclosed separately",
        },
        {
            "id": "IND-02",
            "name": "Weekly inventory reporting completeness",
            "level": "Output",
            "actual": round(snapshot["quality"]["completeness"] * 100, 1),
            "target": 95,
            "unit": "%",
            "basis": "Validated reports / expected reports, latest 12 weeks",
        },
        {
            "id": "IND-05",
            "name": "Redistribution proposals with a recorded review",
            "level": "Process",
            "actual": reviews,
            "target": len(planner["recommendations"]),
            "unit": "proposals",
            "basis": "Append-only review decisions; review does not execute a transfer",
        },
    ]
    for item in indicators:
        item["achievement"] = round(item["actual"] / item["target"] * 100, 1) if item["target"] else None
        item["status"] = (
            "on_track"
            if item["achievement"] is not None and item["achievement"] >= 100
            else "at_risk"
            if item["achievement"] is not None and item["achievement"] >= 85
            else "off_track"
            if item["target"]
            else "not_assessed"
        )
    issues = [
        {
            "id": "ISS-01",
            "issue": "Rural delivery follow-up unresolved",
            "owner": "Logistics lead",
            "status": "open",
            "severity": "high",
            "opened": "2026-10-23",
            "due": (cutoff + timedelta(days=3)).isoformat(),
            "action": "Confirm dispatch dates for overdue orders; validate feasible redistribution",
        },
        {
            "id": "ISS-03",
            "issue": "Gidan reporting gaps limit decisions",
            "owner": "Data officer",
            "status": "open",
            "severity": "high",
            "opened": "2026-10-26",
            "due": "2026-11-05",
            "action": "Reconcile the missing source registers before proposing transfers",
        },
        {
            "id": "ISS-05",
            "issue": "Review protocol signed off",
            "owner": "District supply manager",
            "status": "closed",
            "severity": "low",
            "opened": "2026-09-07",
            "due": "2026-09-25",
            "action": "Protocol filed with district supply procedures",
        },
    ]
    return {
        "project": {
            "title": "Kawara Essential Medicines Supply Plan",
            "code": "KEMAP-2026",
            "donor": "Health Access Partnership (illustrative)",
            "implementer": "District supply team",
            "period": "August–November 2026",
            "governance": "District supply committee; programme director accountable; district pharmacist reviews proposals",
            "currency": "USD",
            "synthetic": True,
        },
        "activities": activities,
        "budget": budget,
        "indicators": indicators,
        "issues": issues,
        "budget_totals": {
            key: sum(x[key] for x in budget) for key in ("allocated", "spent", "committed", "planned_to_date")
        },
    }
