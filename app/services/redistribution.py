"""Pack-aligned redistribution with shared donor reservations and hard expiry gates."""

import hashlib
import math
from datetime import date

from app.core.config import POLICY


def feasible_quantity(donor: dict, recipient: dict, cutoff: date, reserved: int = 0) -> int:
    """Bound a proposal by safety, recipient need, shelf life and prior reservations."""
    if donor["facility_id"] == recipient["facility_id"] or donor["medicine_id"] != recipient["medicine_id"]:
        return 0
    if donor["quality"] not in ("strong", "acceptable") or recipient["quality"] not in (
        "strong",
        "acceptable",
    ):
        return 0
    if donor["adc"] <= 0 or recipient["adc"] <= 0 or not donor["expiry_date"] or not recipient["expiry_date"]:
        return 0
    if donor["stock"] is None or recipient["stock"] is None:
        return 0
    remaining = (date.fromisoformat(donor["expiry_date"]) - cutoff).days - POLICY["transport_buffer_days"]
    if remaining < donor["minimum_shelf_life_days"]:
        return 0
    excess = max(0, donor["stock"] - reserved - donor["adc"] * donor["safety_days"])
    need = max(0, recipient["adc"] * POLICY["recipient_target_days"] - recipient["stock"])
    usable_before_expiry = max(0, recipient["adc"] * remaining - recipient["stock"])
    raw = min(excess, need, usable_before_expiry)
    return int(raw // donor["pack_size"]) * donor["pack_size"]


def distance(a: dict, b: dict) -> float:
    """Haversine straight-line synthetic distance; not a road-cost estimate."""
    lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dlat, dlon = lat2 - lat1, math.radians(b["longitude"] - a["longitude"])
    return round(
        6371
        * 2
        * math.asin(
            math.sqrt(math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        ),
        1,
    )


def plan(snapshot: dict) -> dict:
    """Propose one donor per recipient, reserving quantities across the entire plan."""
    cutoff = date.fromisoformat(snapshot["context"]["cutoff"])
    reserved: dict[str, int] = {}
    recommendations, withheld = [], []
    pairs = snapshot["pairs"]
    for recipient in pairs:
        if recipient["risk"] == "not_assessed":
            withheld.append(
                {
                    "finding_id": recipient["finding_id"],
                    "facility": recipient["facility"],
                    "medicine": recipient["medicine"],
                    "reason": recipient["warnings"][0]
                    if recipient["warnings"]
                    else "Positive consumption and sufficient reporting evidence required",
                }
            )
            continue
        if recipient["risk"] not in ("high", "medium"):
            continue
        candidates = []
        for donor in pairs:
            quantity = feasible_quantity(donor, recipient, cutoff, reserved.get(donor["finding_id"], 0))
            if quantity:
                km = distance(donor, recipient)
                # Urgency is handled by recipient ordering. Then maximise cover gain,
                # favour near-expiry use, and minimise synthetic straight-line distance.
                score = quantity / recipient["adc"] + (5 if donor["near_expiry"] else 0) - km * 0.1
                candidates.append((score, donor["finding_id"], donor, quantity, km))
        if not candidates:
            withheld.append(
                {
                    "finding_id": recipient["finding_id"],
                    "facility": recipient["facility"],
                    "medicine": recipient["medicine"],
                    "reason": "No donor meets safety stock, expiry, pack size and data-quality constraints.",
                }
            )
            continue
        _, _, donor, quantity, km = max(candidates, key=lambda c: (c[0], c[1]))
        before_reserved = reserved.get(donor["finding_id"], 0)
        reserved[donor["finding_id"]] = before_reserved + quantity
        rid = (
            "REC-"
            + hashlib.sha256(
                f"{snapshot['context']['import_id']}-{snapshot['context']['window']}-{recipient['finding_id']}-{donor['finding_id']}".encode()
            ).hexdigest()[:12]
        )
        recommendations.append(
            {
                "recommendation_id": rid,
                "version": 1,
                "status": "pending",
                "quantity": quantity,
                "max_quantity": quantity,
                "pack_size": donor["pack_size"],
                "medicine": donor["medicine"],
                "medicine_id": donor["medicine_id"],
                "recipient": recipient["facility"],
                "recipient_id": recipient["facility_id"],
                "finding_id": recipient["finding_id"],
                "donor": donor["facility"],
                "donor_id": donor["facility_id"],
                "recipient_before": recipient["cover"],
                "recipient_after": round((recipient["stock"] + quantity) / recipient["adc"], 2),
                "donor_before": donor["cover"],
                "donor_after": round((donor["stock"] - before_reserved - quantity) / donor["adc"], 2),
                "reserved_before": before_reserved,
                "donor_adc": donor["adc"],
                "recipient_adc": recipient["adc"],
                "donor_stock": donor["stock"],
                "recipient_stock": recipient["stock"],
                "safety_days": donor["safety_days"],
                "expiry_date": donor["expiry_date"],
                "shelf_life_days": (date.fromisoformat(donor["expiry_date"]) - cutoff).days,
                "near_expiry": bool(donor["near_expiry"]),
                "distance_km": km,
                "risk": recipient["risk"],
                "reason": "Protect the recipient's next 30 days while preserving donor safety stock.",
                "constraints": [
                    "Donor safety stock preserved across all proposals",
                    "Quantity is a whole pack multiple",
                    "Stock can be consumed before expiry with a 3-day transport buffer",
                    "Both facilities meet evidence requirements",
                ],
                "warnings": [
                    "Straight-line distance is a synthetic proxy; confirm transport and storage conditions.",
                    "Cold-chain feasibility must be confirmed by a pharmacist.",
                ]
                if donor["medicine_id"] == "M04"
                else [
                    "Straight-line distance is a synthetic proxy; confirm transport and storage conditions."
                ],
            }
        )
    return {"recommendations": recommendations, "withheld": withheld}


def validate_review(recommendation: dict, request: dict) -> None:
    """An edited quantity may only reduce the original reserved, feasible proposal."""
    if not request.get("acknowledged"):
        raise ValueError("Acknowledge that this records a review and does not move stock")
    quantity = request.get("quantity")
    if request["decision"] == "edited":
        if quantity is None or quantity <= 0 or quantity > recommendation["max_quantity"]:
            raise ValueError("Edited quantity exceeds the safe reserved maximum")
        if quantity % recommendation["pack_size"]:
            raise ValueError("Edited quantity must be a whole pack-size multiple")
    elif quantity is not None:
        raise ValueError("Quantity is only permitted for an edited review")


def attach_reviews(planned: dict, reviews: dict) -> dict:
    """Layer append-only review decisions over immutable analytical proposals."""
    result = []
    for original in planned["recommendations"]:
        item = dict(original)
        review = reviews.get(item["recommendation_id"])
        if review:
            item.update(status=review["decision"], version=review["version"], review=review)
            if review["decision"] == "edited":
                item["reviewed_quantity"] = review["quantity"]
                item["reviewed_recipient_after"] = round(
                    (item["recipient_stock"] + review["quantity"]) / item["recipient_adc"], 2
                )
                item["reviewed_donor_after"] = round(
                    (item["donor_stock"] - item["reserved_before"] - review["quantity"]) / item["donor_adc"],
                    2,
                )
        result.append(item)
    return {**planned, "recommendations": result}
