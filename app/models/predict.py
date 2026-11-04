"""Safe logistic inference from a checksum-verified numeric JSON artifact."""

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import ROOT

FEATURES = [
    "cover",
    "stock",
    "adc",
    "trend",
    "lead_time",
    "completeness",
    "previous_stockout_days",
    "near_expiry",
    "window",
]
SCHEMA_HASH = hashlib.sha256(json.dumps(FEATURES).encode()).hexdigest()


def _read_model(path=None) -> Optional[dict]:
    """Refuse unknown schemas, unapproved models, tampering or malformed coefficients."""
    path = path or ROOT / "model_artifacts/active.json"
    try:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != path.with_suffix(".sha256").read_text().strip():
            return None
        model = json.loads(raw)
        if not model["approved"] or model["schema_hash"] != SCHEMA_HASH:
            return None
        for key in ("coefficient", "mean", "scale", "median"):
            if len(model[key]) != len(FEATURES) or not all(math.isfinite(x) for x in model[key]):
                return None
        if not all(x > 0 for x in model["scale"]) or not math.isfinite(model["intercept"]):
            return None
        if model.get("algorithm") == "gradient_boosting":
            if not 0 < model["learning_rate"] <= 1 or not 0 < len(model["trees"]) <= 500:
                return None
            for tree in model["trees"]:
                size = len(tree["value"])
                if not 0 < size <= 512 or any(
                    len(tree[key]) != size for key in ("left", "right", "feature", "threshold")
                ):
                    return None
                for i in range(size):
                    if not math.isfinite(tree["value"][i]) or not math.isfinite(tree["threshold"][i]):
                        return None
                    if tree["left"][i] != -1 and not (
                        i < tree["left"][i] < size
                        and i < tree["right"][i] < size
                        and 0 <= tree["feature"][i] < len(FEATURES)
                    ):
                        return None
        return model
    except (OSError, ValueError, KeyError, TypeError):
        return None


@lru_cache(maxsize=8)
def _cached_model(path: str, modified: int, checksum_modified: int):
    return _read_model(Path(path))


def load_model(path=None) -> Optional[dict]:
    """Cache verified immutable artifacts; invalidate on artifact or checksum change."""
    path = Path(path) if path else ROOT / "model_artifacts/active.json"
    try:
        return _cached_model(
            str(path), path.stat().st_mtime_ns, path.with_suffix(".sha256").stat().st_mtime_ns
        )
    except OSError:
        return None


def predict(features: list, path=None) -> Optional[dict]:
    """Return advisory probability only; no safety decisions are delegated to ML."""
    model = load_model(path)
    if model is None or len(features) != len(FEATURES):
        return None
    clean = []
    for i, value in enumerate(features):
        value = model["median"][i] if value is None else value
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        clean.append(value)
    transformed = [(v - m) / s for v, m, s in zip(clean, model["mean"], model["scale"])]
    contributions = [c * v for c, v in zip(model["coefficient"], transformed)]
    logit = model["intercept"] + sum(contributions)
    if model.get("algorithm") == "gradient_boosting":
        contributions = [0.0] * len(FEATURES)
        for tree in model["trees"]:
            node = 0
            while tree["left"][node] != -1:
                feature = tree["feature"][node]
                child = (
                    tree["left"][node]
                    if transformed[feature] <= tree["threshold"][node]
                    else tree["right"][node]
                )
                contributions[feature] += model["learning_rate"] * (
                    tree["value"][child] - tree["value"][node]
                )
                node = child
            logit += model["learning_rate"] * tree["value"][node]
    probability = 1 / (1 + math.exp(-max(-700, min(700, logit))))
    factors = sorted(
        [
            {
                "feature": name,
                "value": clean[i],
                "contribution": round(contributions[i], 6),
                "direction": "raises estimate" if contributions[i] > 0 else "reduces estimate",
            }
            for i, name in enumerate(FEATURES)
            if abs(contributions[i]) > 1e-8
        ],
        key=lambda f: abs(f["contribution"]),
        reverse=True,
    )[:4]
    return {
        "probability": round(probability, 5),
        "version": model["version"],
        "factors": factors,
        "high_threshold": model.get("threshold", 0.6),
        "explanation_method": "Additive tree-path contributions in log-odds; order-dependent, not causal"
        if model.get("algorithm") == "gradient_boosting"
        else "Additive logistic coefficient contributions in log-odds relative to training mean; not causal",
    }
