"""Load the analytical policy as a single versioned source of truth."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / "app/core/policy.json").read_text())
