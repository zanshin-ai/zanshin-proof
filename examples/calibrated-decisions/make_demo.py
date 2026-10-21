"""Create explicitly synthetic evidence to exercise the policy, not benchmark a model."""

from __future__ import annotations

import argparse
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


def make_decisions() -> dict:
    evidence = make_demo()
    # Exactly 99/100 correct at confidence .99: calibrated synthetic observations.
    return {
        "version": 1,
        "provenance": evidence["provenance"],
        "facts": evidence["facts"],
        "evaluation": {"bin_count": 10, "automation_threshold": 0.9},
        "records": [
            {"id": str(i), "probability": 0.99, "label": int(i != 0),
             "baseline_probability": 0.95, "latency_ms": 180}
            for i in range(100)
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", action="store_true", help="emit labeled decision records")
    args = parser.parse_args()
    print(json.dumps(make_decisions() if args.decisions else make_demo(), indent=2))
