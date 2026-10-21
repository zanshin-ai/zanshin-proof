"""Create explicitly synthetic evidence to exercise the policy, not benchmark a model."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path


def make_demo() -> dict:
    source = Path(__file__).resolve()
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source.parent, text=True
    ).strip()
    return {
        "provenance": {
            "commit_sha": revision,
            "collected_at": datetime.now(UTC).isoformat(),
            "collector": {"name": "synthetic-policy-demo", "version": "1"},
            "model": {"name": "synthetic-fixture-no-model-called", "version": "1"},
            "run": {"system": "local-synthetic-demo", "id": str(uuid.uuid4())},
            "sources": [{
                "type": "file",
                "uri": source.as_uri(),
                "version": hashlib.sha256(source.read_bytes()).hexdigest(),
            }],
        },
        "facts": {
            "synthetic": True,
            "typed_output_valid": True,
            "held_out_evaluation": True,
        },
        "metrics": {
            "baseline": {"accuracy": 0.94},
            "candidate": {
                "sample_count": 1000,
                "accuracy": 0.95,
                "ece": 0.025,
                "brier": 0.06,
                "selective_error": 0.01,
                "coverage": 0.70,
                "p95_latency_ms": 180,
            },
        },
    }


if __name__ == "__main__":
    print(json.dumps(make_demo(), indent=2))
