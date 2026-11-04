"""Leakage-aware logistic benchmark with purged chronological holdouts; JSON inference artifact."""

import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import ROOT
from app.data.generate import END, VERSION, generate
from app.data.validation import validate_bundle
from app.models.predict import FEATURES, SCHEMA_HASH


def samples() -> list[dict]:
    """Features only use records at/before t; labels require complete future periods."""
    clean = validate_bundle(generate(), END)["data"]
    groups = defaultdict(list)
    for row in clean["inventory"]:
        groups[(row["facility_id"], row["medicine_id"])].append(row)
    facility_map = {f["facility_id"]: f for f in clean["facilities"]}
    medicine_map = {m["medicine_id"]: m for m in clean["medicines"]}
    result = []
    for (fid, mid), rows in groups.items():
        rows.sort(key=lambda r: r["reporting_date"])
        for row in rows:
            cutoff = date.fromisoformat(row["reporting_date"])
            prior = [
                r
                for r in rows
                if (cutoff - timedelta(weeks=11)).isoformat() <= r["reporting_date"] <= cutoff.isoformat()
            ]
            short = prior[-4:]
            if len(prior) < 8:
                continue
            adc = sum(r["quantity_dispensed"] for r in short) / (len(short) * 7)
            long_adc = sum(r["quantity_dispensed"] for r in prior) / (len(prior) * 7)
            cover = row["closing_balance"] / adc if adc else np.nan
            for window in (7, 14, 30):
                if cutoff + timedelta(days=window) > END:
                    continue
                future = [
                    r
                    for r in rows
                    if cutoff.isoformat()
                    < r["reporting_date"]
                    <= (cutoff + timedelta(days=window)).isoformat()
                ]
                if len(future) != window // 7:
                    continue
                label = int(any(r["stockout_days"] > 0 for r in future))
                f, m = facility_map[fid], medicine_map[mid]
                result.append(
                    {
                        "date": cutoff.isoformat(),
                        "features": [
                            cover,
                            row["closing_balance"],
                            adc,
                            adc / long_adc - 1 if long_adc else np.nan,
                            f["lead_time_days"],
                            len(prior) / 12,
                            sum(r["stockout_days"] for r in prior),
                            row["quantity_near_expiry"],
                            window,
                        ],
                        "label": label,
                        "baseline": int(cover < window) if adc else 0,
                        "location_type": f["location_type"],
                        "facility_type": f["facility_type"],
                        "medicine_category": m["category"],
                        "quality": "complete" if len(prior) == 12 else "limited",
                        "feature_max_date": row["reporting_date"],
                        "label_end": (cutoff + timedelta(days=window)).isoformat(),
                    }
                )
    return result


def time_split(rows: list[dict]) -> dict:
    """Purge label horizons at boundaries; never fit preprocessing on holdouts."""
    start = END - timedelta(weeks=59)
    train_end = start + timedelta(weeks=31)
    val_start, val_end = start + timedelta(weeks=37), start + timedelta(weeks=43)
    test_start = start + timedelta(weeks=49)
    return {
        "train": [r for r in rows if r["date"] <= train_end.isoformat()],
        "validation": [r for r in rows if val_start.isoformat() <= r["date"] <= val_end.isoformat()],
        "test": [r for r in rows if r["date"] >= test_start.isoformat()],
    }


def metrics(y, prob, threshold=0.6) -> dict:
    pred = np.asarray(prob) >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y, prob)) if sum(y) else 0,
        "brier": float(brier_score_loss(y, prob)),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "false_negative_rate": float(fn / max(fn + tp, 1)),
        "false_positive_rate": float(fp / max(fp + tn, 1)),
        "alert_count": int(sum(pred)),
        "alert_rate": float(np.mean(pred)),
    }


def train() -> dict:
    """Train once, choose threshold using validation, and report the test holdout once."""
    rows = samples()
    splits = time_split(rows)
    x = {key: np.asarray([r["features"] for r in subset], dtype=float) for key, subset in splits.items()}
    y = {key: np.asarray([r["label"] for r in subset]) for key, subset in splits.items()}
    models = {
        "logistic": make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(max_iter=1500, random_state=42),
        ),
        "gradient_boosting": make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            GradientBoostingClassifier(n_estimators=90, max_depth=2, learning_rate=0.05, random_state=42),
        ),
    }
    validation = {}
    for name, candidate in models.items():
        candidate.fit(x["train"], y["train"])
        scores = candidate.predict_proba(x["validation"])[:, 1]
        options = [
            {"threshold": threshold, **metrics(y["validation"], scores, threshold)}
            for threshold in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
        ]
        chosen_option = min(
            options,
            key=lambda c: (3 * c["confusion_matrix"][1][0] + c["confusion_matrix"][0][1], -c["recall"]),
        )
        validation[name] = {"operating_point": chosen_option, "candidates": options}
    # Select on validation only: favour ranking (PR-AUC) with calibration as tie-breaker.
    selected = max(
        validation,
        key=lambda name: (
            validation[name]["operating_point"]["pr_auc"],
            -validation[name]["operating_point"]["brier"],
        ),
    )
    pipeline = models[selected]
    chosen = validation[selected]["operating_point"]
    candidates = validation[selected]["candidates"]
    threshold = chosen["threshold"]
    baseline_val = metrics(y["validation"], [r["baseline"] for r in splits["validation"]], 0.5)
    # Promotion is for probability ranking/calibration only. The baseline alert
    # remains a hard lower bound, preserving its recall in the combined system.
    approved = chosen["pr_auc"] > baseline_val["pr_auc"] and chosen["brier"] < baseline_val["brier"]
    probability = pipeline.predict_proba(x["test"])[:, 1]
    test_metrics = metrics(y["test"], probability, threshold)
    baseline_test = metrics(y["test"], [r["baseline"] for r in splits["test"]], 0.5)
    calibration_true, calibration_pred = calibration_curve(
        y["test"], probability, n_bins=8, strategy="quantile"
    )
    subgroups = {}
    for key in ("location_type", "facility_type", "medicine_category", "quality"):
        subgroups[key] = {}
        for group in sorted({r[key] for r in splits["test"]}):
            mask = np.asarray([r[key] == group for r in splits["test"]])
            subgroups[key][group] = {
                "n": int(sum(mask)),
                "positives": int(sum(y["test"][mask])),
                "small_group": bool(sum(mask) < 100),
                **metrics(y["test"][mask], probability[mask], threshold),
            }
    robustness = {}
    for kind in ("missing_stock", "consumption_spike", "zero_consumption"):
        perturbed = x["test"].copy()
        if kind == "missing_stock":
            perturbed[:, :2] = np.nan
        elif kind == "consumption_spike":
            perturbed[:, 2] *= 2
            perturbed[:, 0] /= 2
        else:
            perturbed[:, 2] = 0
            perturbed[:, 0] = np.nan
        robustness[kind] = metrics(y["test"], pipeline.predict_proba(perturbed)[:, 1], threshold)
    model = {
        "version": selected + "-1.1.0",
        "algorithm": selected,
        "schema_hash": SCHEMA_HASH,
        "features": FEATURES,
        "approved": approved,
        "median": pipeline[0].statistics_.tolist(),
        "mean": pipeline[1].mean_.tolist(),
        "scale": pipeline[1].scale_.tolist(),
        "coefficient": pipeline[2].coef_[0].tolist() if selected == "logistic" else [0.0] * len(FEATURES),
        "intercept": float(pipeline[2].intercept_[0])
        if selected == "logistic"
        else float(np.log(pipeline[2].init_.class_prior_[1] / pipeline[2].init_.class_prior_[0])),
        "seed": 42,
        "generator_version": VERSION,
        "threshold": threshold,
        "calibration": "Uncalibrated model probabilities; empirical calibration bins and Brier score disclosed",
        "training_distribution": {
            feature: {"mean": float(np.nanmean(x["train"][:, i])), "std": float(np.nanstd(x["train"][:, i]))}
            for i, feature in enumerate(FEATURES)
        },
        "training_cutoff": max(r["date"] for r in splits["train"]),
    }
    if selected == "gradient_boosting":
        model["learning_rate"] = 0.05
        model["trees"] = [
            {
                "left": estimator[0].tree_.children_left.tolist(),
                "right": estimator[0].tree_.children_right.tolist(),
                "feature": estimator[0].tree_.feature.tolist(),
                "threshold": estimator[0].tree_.threshold.tolist(),
                "value": estimator[0].tree_.value[:, 0, 0].tolist(),
            }
            for estimator in pipeline[2].estimators_
        ]
    output = ROOT / "model_artifacts"
    output.mkdir(exist_ok=True)
    artifact = json.dumps(model, indent=2).encode()
    (output / "active.json").write_bytes(artifact)
    (output / "active.sha256").write_text(hashlib.sha256(artifact).hexdigest())
    evaluation = {
        "version": model["version"],
        "data": VERSION,
        "synthetic": True,
        "schema_hash": SCHEMA_HASH,
        "split": {
            "purge_days": 30,
            **{
                key: {
                    "n": len(subset),
                    "start": min(r["date"] for r in subset),
                    "end": max(r["date"] for r in subset),
                }
                for key, subset in splits.items()
            },
        },
        "threshold": threshold,
        "threshold_rationale": "Validation-only minimum cost: missed stock-out weighted 3; additional alert weighted 1. Risk display conservatively retains deterministic baseline alerts.",
        "threshold_candidates": candidates,
        "validation_models": validation,
        "selected_model": selected,
        "validation_baseline": baseline_val,
        "test": {
            "sample_count": len(splits["test"]),
            "model": test_metrics,
            "baseline": baseline_test,
            "by_horizon": {
                str(h): metrics(
                    y["test"][x["test"][:, -1] == h], probability[x["test"][:, -1] == h], threshold
                )
                for h in (7, 14, 30)
            },
            "combined_alert_rule": metrics(
                y["test"],
                np.maximum(probability, np.array([r["baseline"] for r in splits["test"]], dtype=float)),
                threshold,
            ),
            "calibration": {
                "mean_prediction": calibration_pred.tolist(),
                "observed_rate": calibration_true.tolist(),
            },
        },
        "subgroups": subgroups,
        "robustness": robustness,
        "promotion": {
            "approved": approved,
            "reason": "Promoted for advisory probability ranking: validation PR-AUC improves and Brier score decreases versus baseline. Baseline alerts remain a hard lower bound on the risk band."
            if approved
            else "Validation ranking/calibration criteria not met; baseline remains active.",
        },
        "limitations": "Synthetic observations from one fictional district. Reported statistics describe the standalone model, not the conservative combined UI rule. Sparse groups do not establish fairness. Perturbation tests are stress scenarios, not real-world estimates. Zero-consumption and insufficient-quality pairs remain gated in the application.",
    }
    (output / "evaluation.json").write_text(json.dumps(evaluation, indent=2))
    return evaluation


if __name__ == "__main__":
    result = train()
    print(
        json.dumps(
            {"promotion": result["promotion"], "test": result["test"], "threshold": result["threshold"]},
            indent=2,
        )
    )
