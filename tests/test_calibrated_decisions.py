"""Exercise the documented decision policy through its public CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from zanshin_proof.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [
        (None, None, 0),
        ("ece", 0.20, 1),
        ("brier", 0.30, 1),
        ("accuracy", 0.80, 1),
        ("selective_error", 0.10, 1),
        ("coverage", 0.0, 1),
        ("sample_count", 10, 1),
        ("p95_latency_ms", 900, 1),
        ("selective_error", None, 1),
    ],
)
def test_decision_policy(tmp_path, metric, value, expected):
    evidence = json.loads(subprocess.check_output(
        [sys.executable, str(ROOT / "examples/calibrated-decisions/make_demo.py")],
        text=True,
    ))
    assert evidence["facts"]["synthetic"] is True
    if metric:
        if value is None:
            del evidence["metrics"]["candidate"][metric]
        else:
            evidence["metrics"]["candidate"][metric] = value
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence))
    output = tmp_path / "report.json"
    assert main([
        "evaluate", "--policy", str(ROOT / "examples/calibrated-decisions/policy.yml"),
        "--evidence", str(path), "--output", str(output),
    ]) == expected
    report = json.loads(output.read_text())
    assert report["provenance"] == evidence["provenance"]
    assert report["verdict"] == ("pass" if expected == 0 else "fail")
