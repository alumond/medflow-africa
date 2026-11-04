"""Bounded CSV parsing and layered, non-corrective validation."""

import csv
import hashlib
import io
from collections import Counter
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.core.config import POLICY
from app.core.schemas import Facility, Inventory, Medicine, Order

CONTRACTS: dict[str, Any] = {
    "facilities": Facility,
    "medicines": Medicine,
    "inventory": Inventory,
    "orders": Order,
}
PROHIBITED = {
    "patient",
    "patient_id",
    "patient_name",
    "diagnosis",
    "clinical_notes",
    "email",
    "phone",
    "national_id",
    "date_of_birth",
    "address",
    "treatment",
}


def parse_csv(content: bytes, entity: str) -> list[dict]:
    """Reject unsafe structures before processing individual operational rows."""
    if entity not in CONTRACTS:
        raise ValueError("Unknown dataset type")
    if len(content) > POLICY["max_upload_bytes"]:
        raise ValueError("File exceeds the 8 MB limit")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers):
            raise ValueError("Duplicate column names are not supported")
        if any(
            any(term == h.lower() or h.lower().startswith(term + "_") for term in PROHIBITED) for h in headers
        ):
            raise ValueError("Patient or personal-data columns are prohibited")
        contract = CONTRACTS[entity]
        required = {k for k, f in contract.model_fields.items() if f.is_required()}
        if not required.issubset(headers):
            raise ValueError("Missing required columns: " + ", ".join(sorted(required - set(headers))))
        if set(headers) - set(contract.model_fields):
            raise ValueError(
                "Unknown columns: " + ", ".join(sorted(set(headers) - set(contract.model_fields)))
            )
        result: list[dict] = []
        for row in reader:
            if len(result) >= POLICY["max_rows"]:
                raise ValueError("Row limit exceeded")
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed CSV row or delimiter")
            result.append(
                {
                    k: None if v == "" and k in ("expiry_date", "actual_delivery_date") else v
                    for k, v in row.items()
                }
            )
        return result
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Use UTF-8 comma-separated CSV files") from exc


def validate_bundle(bundle: dict, cutoff: date) -> dict:
    """Validate references first; quarantine every duplicate business-key instance."""
    clean: dict[str, list[dict]] = {}
    rejected: list[dict] = []
    for entity, contract in CONTRACTS.items():
        rows = bundle.get(entity, [])
        counts = Counter(_key(entity, row) for row in rows)
        id_field = {
            "facilities": "facility_id",
            "medicines": "medicine_id",
            "inventory": "record_id",
            "orders": "order_id",
        }[entity]
        id_counts = Counter(str(row.get(id_field, "")) for row in rows)
        clean[entity] = []
        for index, row in enumerate(rows, 2):
            try:
                if counts[_key(entity, row)] > 1 or id_counts[str(row.get(id_field, ""))] > 1:
                    raise ValueError("DUPLICATE: repeated identifier or business key")
                parsed = contract.model_validate(row)
                item = parsed.model_dump(mode="json")
                if entity in ("inventory", "orders"):
                    for reference, field in (("facilities", "facility_id"), ("medicines", "medicine_id")):
                        if item[field] not in {x[field] for x in clean[reference] if x["active"]}:
                            raise ValueError("REFERENCE: unknown or inactive " + field)
                    for field in ("reporting_date", "order_date", "actual_delivery_date"):
                        if item.get(field) and date.fromisoformat(item[field]) > cutoff:
                            raise ValueError("FUTURE_DATE: reported event exceeds dataset cut-off")
                clean[entity].append(item)
            except (ValidationError, ValueError) as exc:
                reason = str(exc)
                rule = next(
                    (
                        x
                        for x in (
                            "DUPLICATE",
                            "REFERENCE",
                            "BALANCE",
                            "EXPIRY_QUANTITY",
                            "EXPIRY_DATE",
                            "FUTURE_DATE",
                            "ORDER_DATE",
                            "DELIVERY_DATE",
                            "FULFILMENT",
                        )
                        if x in reason
                    ),
                    "SCHEMA",
                )
                field = (
                    "record"
                    if not isinstance(exc, ValidationError)
                    else ".".join(map(str, exc.errors()[0]["loc"])) or "record"
                )
                rejected.append(
                    {
                        "entity": entity,
                        "row": index,
                        "facility_id": _safe(row.get("facility_id")),
                        "medicine_id": _safe(row.get("medicine_id")),
                        "reporting_date": _safe(row.get("reporting_date")),
                        "rule": rule,
                        "field": field,
                        "reason": {
                            "SCHEMA": "Invalid or missing field value",
                            "BALANCE": "Closing balance does not reconcile",
                            "DUPLICATE": "Duplicate business key or identifier; all copies quarantined",
                            "REFERENCE": "Unknown or inactive reference",
                            "EXPIRY_QUANTITY": "Near-expiry quantity exceeds stock",
                            "EXPIRY_DATE": "Usable stock is expired",
                            "FUTURE_DATE": "Event occurs after cut-off",
                        }.get(rule, "Order dates or quantities are inconsistent"),
                        "severity": "blocking",
                    }
                )
    total = sum(len(x) for x in bundle.values())
    approved = bool(clean["facilities"] and clean["medicines"] and clean["inventory"])
    return {
        "data": clean,
        "rejected": rejected,
        "total": total,
        "accepted": total - len(rejected),
        "approved": approved,
    }


def _safe(value) -> str:
    value = str(value or "")
    return value[:50] if all(c.isalnum() or c in "_-" for c in value) else "withheld"


def _key(entity: str, row: dict) -> tuple:
    return tuple(
        str(row.get(k, ""))
        for k in (
            {
                "facilities": ["facility_id"],
                "medicines": ["medicine_id"],
                "inventory": ["facility_id", "medicine_id", "reporting_date"],
                "orders": ["order_id"],
            }[entity]
        )
    )


def checksum(bundle: dict) -> str:
    """Hash canonical source content, independent of dictionary insertion order."""
    import json

    return hashlib.sha256(json.dumps(bundle, sort_keys=True, default=str).encode()).hexdigest()
