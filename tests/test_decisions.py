"""Numerical and public CLI contracts for binary decision evaluation."""

import json
import runpy
from copy import deepcopy
from pathlib import Path

import pytest

from zanshin_proof.cli import main
from zanshin_proof.decisions import compute_evidence
from zanshin_proof.evaluator import EvidenceError
from zanshin_proof.schema import validate_document

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def document():
    return runpy.run_path(str(ROOT / "examples/calibrated-decisions/make_demo.py"))[
        "make_decisions"
    ]()


def test_hand_calculated_metrics(document):
    document["records"] = [
        {"id": "a", "probability": 0.9, "label": 1, "baseline_probability": 0.1,
         "latency_ms": 10},
        {"id": "b", "probability": 0.8, "label": 0, "baseline_probability": 0.2,
         "latency_ms": 20},
        {"id": "c", "probability": 0.2, "label": 0, "baseline_probability": 0.8,
         "latency_ms": 30},
        {"id": "d", "probability": 0.5, "label": 1, "baseline_probability": 0.5,
         "latency_ms": 40},
    ]
    document["evaluation"] = {"bin_count": 2, "automation_threshold": 0.8}
    before = deepcopy(document)
    evidence = compute_evidence(document)
    c = evidence["metrics"]["candidate"]
    assert c["brier"] == pytest.approx(0.235)
    assert c["accuracy"] == 0.75
    assert c["ece"] == pytest.approx(0)
    assert c["coverage"] == 0.75
    assert c["selective_error"] == pytest.approx(1 / 3)
    assert c["automated_count"] == 3
    assert c["p95_latency_ms"] == 40
    assert c["calibration_bins"][0]["mean_confidence"] is None
    assert c["calibration_bins"][1]["count"] == 4
    assert evidence["metrics"]["baseline"]["accuracy"] == 0.5
    assert evidence["provenance"] == document["provenance"]
    assert evidence["facts"] == document["facts"]
    assert document == before
    assert compute_evidence(document) == evidence
    validate_document(evidence, "evidence")
    evidence["provenance"]["model"]["name"] = "changed"
    assert document == before


def test_edges_and_empty_selection(document):
    document["records"] = [
        {"id": "a", "probability": 0, "label": 0},
        {"id": "b", "probability": 1, "label": 1},
        {"id": "c", "probability": 0.5, "label": 0},
    ]
    document["evaluation"] = {"bin_count": 10, "automation_threshold": 1}
    c = compute_evidence(document)["metrics"]["candidate"]
    assert c["ece"] == pytest.approx(1 / 6)
    assert c["brier"] == pytest.approx(1 / 12)
    assert c["accuracy"] == pytest.approx(2 / 3)
    assert c["calibration_bins"][5]["count"] == 1
    assert c["calibration_bins"][9]["count"] == 2
    assert c["selective_error"] == 0
    assert "p95_latency_ms" not in c
    document["records"] = [document["records"][-1]]
    evidence = compute_evidence(document)
    c = evidence["metrics"]["candidate"]
    assert c["coverage"] == 0
    assert c["automated_count"] == 0
    assert "selective_error" not in c
    assert "baseline" not in evidence["metrics"]


def test_perfectly_wrong_and_correct(document):
    document["records"] = [{"id": "a", "probability": 1, "label": 0}]
    c = compute_evidence(document)["metrics"]["candidate"]
    assert (c["ece"], c["brier"], c["selective_error"]) == (1, 1, 1)
    document["records"][0]["label"] = 1
    c = compute_evidence(document)["metrics"]["candidate"]
    assert (c["ece"], c["brier"], c["selective_error"]) == (0, 0, 0)


@pytest.mark.parametrize("value", [-0.1, 1.1, True, "0.5", None, float("nan"), float("inf")])
def test_invalid_probability(document, value):
    document["records"][0]["probability"] = value
    with pytest.raises(EvidenceError):
        compute_evidence(document)


@pytest.mark.parametrize("value", [True, "1", -1, 2, 0.5, None])
def test_invalid_label(document, value):
    document["records"][0]["label"] = value
    with pytest.raises(EvidenceError):
        compute_evidence(document)


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(records=[]),
    lambda d: d.update(version=2),
    lambda d: d["records"][0].update(id="1"),
    lambda d: d["records"][0].pop("label"),
    lambda d: d["records"][0].pop("baseline_probability"),
    lambda d: d["records"][0].pop("latency_ms"),
    lambda d: d["records"][0].update(latency_ms=-1),
    lambda d: d["records"][0].update(latency_ms=float("inf")),
    lambda d: d["evaluation"].update(bin_count=0),
    lambda d: d["evaluation"].update(bin_count=1001),
    lambda d: d["evaluation"].update(bin_count=True),
    lambda d: d["evaluation"].update(bin_count=1.5),
    lambda d: d["evaluation"].update(automation_threshold=0.4),
    lambda d: d["evaluation"].update(automation_threshold=1.1),
    lambda d: d["evaluation"].update(automation_threshold=float("nan")),
    lambda d: d["provenance"].pop("commit_sha"),
    lambda d: d.update(metrics={"candidate": {"ece": 0}}),
])
def test_invalid_documents(document, mutation):
    mutation(document)
    with pytest.raises(EvidenceError):
        compute_evidence(document)


def test_nearest_rank_and_fingerprint(document):
    for i, row in enumerate(document["records"]):
        row["latency_ms"] = i + 1
    first = compute_evidence(document)
    assert first["metrics"]["candidate"]["p95_latency_ms"] == 95
    document["evaluation"]["bin_count"] = 5
    second = compute_evidence(document)
    assert first["metrics"]["computation"]["input_sha256"] != (
        second["metrics"]["computation"]["input_sha256"]
    )


@pytest.mark.parametrize("mode, code", [("pass", 0), ("wrong", 1), ("abstain", 1), ("bad", 2)])
def test_cli_decisions(document, tmp_path, mode, code):
    if mode == "wrong":
        for row in document["records"]:
            row["label"] = 0
    elif mode == "abstain":
        document["evaluation"]["automation_threshold"] = 1
    elif mode == "bad":
        document["records"][0]["probability"] = float("nan")
    source, evidence, report = [tmp_path / name for name in ("in.json", "out.json", "report.json")]
    source.write_text(json.dumps(document))
    assert main([
        "evaluate", "--policy", str(ROOT / "examples/calibrated-decisions/policy.yml"),
        "--decisions", str(source), "--evidence-output", str(evidence), "--output", str(report),
    ]) == code
    if code == 2:
        assert not evidence.exists()
        assert not report.exists()
    else:
        computed = json.loads(evidence.read_text())
        assert computed == compute_evidence(document)
        assert json.loads(report.read_text())["provenance"] == document["provenance"]
        assert main([
            "evaluate", "--policy", str(ROOT / "examples/calibrated-decisions/policy.yml"),
            "--evidence", str(evidence),
        ]) == code


def test_cli_preserves_input(document, tmp_path):
    source = tmp_path / "decisions.json"
    original = json.dumps(document)
    source.write_text(original)
    assert main([
        "evaluate", "--policy", str(ROOT / "examples/calibrated-decisions/policy.yml"),
        "--decisions", str(source), "--output", str(source),
    ]) == 2
    assert source.read_text() == original


def test_weighted_ece_and_boundary_assignment(document):
    document["records"] = [
        {"id": "a", "probability": 0.6, "label": 1},
        {"id": "b", "probability": 0.8, "label": 1},
        {"id": "c", "probability": 0.8, "label": 1},
        {"id": "d", "probability": 0.8, "label": 0},
    ]
    document["evaluation"] = {"bin_count": 5, "automation_threshold": 0.8}
    c = compute_evidence(document)["metrics"]["candidate"]
    # .25 * |.6 - 1| + .75 * |.8 - 2/3| = .20; the global gap is zero.
    assert c["ece"] == pytest.approx(0.20)
    assert c["calibration_bins"][3]["count"] == 1
    assert c["calibration_bins"][4]["count"] == 3
    assert c["coverage"] == 0.75


def test_cli_output_error(document, tmp_path, capsys):
    source = tmp_path / "decisions.json"
    source.write_text(json.dumps(document))
    assert main([
        "evaluate", "--policy", str(ROOT / "examples/calibrated-decisions/policy.yml"),
        "--decisions", str(source), "--evidence-output", str(tmp_path / "missing" / "out.json"),
    ]) == 2
    assert "output error" in capsys.readouterr().err
