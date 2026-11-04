"""Reproducible fictional weekly inventory; scenario truth stays outside model features."""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from app.core.config import POLICY, ROOT

END = date(2026, 11, 1)
VERSION = "synthetic-1.0.0-seed42"


def generate(seed: int = 42) -> dict:
    """Create 60 weeks, ten facilities and ten medicines using a private RNG."""
    rng = random.Random(seed)
    names = [
        "Kawara District Hospital",
        "Central Health Centre",
        "Oke Rural Clinic",
        "Afon Health Centre",
        "Ile Community Clinic",
        "Bode Rural Clinic",
        "Riverbank Health Centre",
        "Asa Community Clinic",
        "Northgate Health Centre",
        "Gidan Rural Clinic",
    ]
    facilities = [
        dict(
            facility_id=f"F{i + 1:02}",
            facility_name=name,
            facility_type="hospital" if i == 0 else "clinic" if i in (2, 4, 5, 7, 9) else "health_centre",
            location_type="rural" if i in (2, 5, 7, 9) else "urban" if i < 2 else "peri_urban",
            latitude=round(8.4 + rng.uniform(-0.16, 0.16), 5),
            longitude=round(4.5 + rng.uniform(-0.16, 0.16), 5),
            lead_time_days=21 if i in (2, 5, 7, 9) else 10,
            reporting_target=0.95,
            active=True,
        )
        for i, name in enumerate(names)
    ]
    definitions = [
        ("Amoxicillin 500 mg", "antibiotic", 100),
        ("Artemether / lumefantrine", "antimalarial", 24),
        ("Oral rehydration salts", "rehydration", 100),
        ("Oxytocin 10 IU", "maternal_health", 10),
        ("Paracetamol 500 mg", "analgesic", 100),
        ("Metformin 500 mg", "chronic_care", 100),
        ("Zinc sulphate 20 mg", "nutrition", 100),
        ("Ceftriaxone 1 g", "antibiotic", 10),
        ("Ferrous sulphate", "maternal_health", 100),
        ("Amlodipine 5 mg", "chronic_care", 100),
    ]
    medicines = [
        dict(
            medicine_id=f"M{i + 1:02}",
            medicine_name=n,
            category=c,
            pack_size=p,
            safety_stock_days=21,
            minimum_shelf_life_days=7,
            active=True,
        )
        for i, (n, c, p) in enumerate(definitions)
    ]
    records: list[dict] = []
    orders: list[dict] = []
    targets = {
        (2, 0): 5.8,
        (5, 1): 8.2,
        (7, 2): 4.5,
        (3, 3): 10.2,
        (4, 4): 12.4,
        (8, 5): 13.2,
        (2, 6): 19,
        (5, 7): 23,
        (9, 0): 3,
    }
    for fi, f in enumerate(facilities):
        for mi, m in enumerate(medicines):
            adc = rng.uniform(12, 65) * (2.1 if fi == 0 else 1)
            stock = int(adc * rng.uniform(25, 70))
            for week in range(60):
                day = END - timedelta(weeks=59 - week)
                # Controlled stochastic replenishment produces actual future stock-out labels.
                opening = stock
                demand = int(adc * 7 * rng.uniform(0.75, 1.3))
                if (fi, mi) == (2, 0) and week >= 56:
                    demand = int(demand * 1.7)
                if (fi, mi) == (6, 9) and week >= 56:
                    demand = 0
                received = (
                    int(adc * rng.uniform(24, 56)) if week % 4 == (fi + mi) % 4 and rng.random() > 0.18 else 0
                )
                available = opening + received
                dispensed = min(demand, available)
                stockout = (
                    min(7, max(1, int(7 * (demand - available) / max(demand, 1))))
                    if demand > available
                    else 0
                )
                stock = available - dispensed
                adjustment = 0
                if week >= 56:
                    target = targets.get((fi, mi), 60 if fi in (0, 1) else 36 + (fi + mi) % 30)
                    desired = int((demand / 7 if demand else adc) * target)
                    adjustment = desired - stock
                    stock = desired
                    stockout = 0
                expiry = END + timedelta(days=45 if fi == 0 and mi in (0, 2) else 240 + mi * 10)
                row: dict = dict(
                    record_id=f"I-{fi:02}-{mi:02}-{week:02}",
                    reporting_date=day.isoformat(),
                    facility_id=f["facility_id"],
                    medicine_id=m["medicine_id"],
                    opening_balance=opening,
                    quantity_received=received,
                    quantity_dispensed=dispensed,
                    adjustments=adjustment,
                    closing_balance=stock,
                    stockout_days=stockout,
                    expiry_date=expiry.isoformat(),
                    quantity_near_expiry=stock if fi == 0 and mi in (0, 2) else 0,
                    report_submitted_on_time=rng.random() > (0.4 if fi == 9 else 0.035),
                )
                if fi == 9 and week % 3 == 0:
                    continue
                if fi == 4 and mi == 5 and week == 59:
                    row["closing_balance"] += 150  # deliberate rejection, never used as valid stock
                records.append(row)
            delayed = (fi, mi) in targets and targets[(fi, mi)] < 14
            orders.append(
                dict(
                    order_id=f"O-{fi:02}-{mi:02}",
                    facility_id=f["facility_id"],
                    medicine_id=m["medicine_id"],
                    order_date=(END - timedelta(days=28)).isoformat(),
                    quantity_ordered=int(adc * 30),
                    expected_delivery_date=(END - timedelta(days=9 if delayed else 14)).isoformat(),
                    actual_delivery_date=None if delayed else (END - timedelta(days=12)).isoformat(),
                    quantity_delivered=0 if delayed else int(adc * 30),
                    order_status="pending" if delayed else "fulfilled",
                )
            )
    return {"facilities": facilities, "medicines": medicines, "inventory": records, "orders": orders}


def write_demo(directory: Path = ROOT / "data/demo") -> None:
    """Write canonical CSVs and the separate scenario manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    for entity, rows in generate().items():
        with (directory / f"{entity}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "seed": POLICY["seed"],
                "cutoff": END.isoformat(),
                "synthetic": True,
                "scenarios": {
                    "surge_late_delivery": "F03/M01",
                    "safe_donor": "F02/M01",
                    "near_expiry": "F01/M01",
                    "weak_evidence": "F10/M01",
                    "invalid_balance": "F05/M06",
                    "zero_consumption": "F07/M10",
                },
            },
            indent=2,
        )
    )
