import json
import sqlite3
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from zanshin_proof.cli import main
from zanshin_proof.evaluator import EvidenceError
from zanshin_proof.policy import load_policy
from zanshin_proof.workspace import RunStore, WorkspaceError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inputs():
    policy = load_policy(ROOT / "examples/recommendation/policy.yml")
    evidence = json.loads((ROOT / "examples/recommendation/evidence.json").read_text())
    return policy, evidence


def test_snapshot_survives_restart_and_input_mutation(tmp_path, inputs):
    policy, evidence = inputs
    store = RunStore(tmp_path / "runs.db")
    run = store.record(policy, evidence, actor="agent:codex")
    original = deepcopy(run)
    evidence["provenance"]["model"]["version"] = "later"
    run["evidence"]["facts"].clear()
    assert RunStore(store.path).get(run["id"]) == original
    assert original["report"]["provenance"] == original["evidence"]["provenance"]
    assert original["actor"] == "agent:codex"
    assert len(original["digests"]["policy"]) == 64


def test_failed_checks_remain_blocked_and_are_saved(tmp_path, inputs):
    policy, evidence = inputs
    evidence["metrics"]["candidate"]["auc"] = 0
    store = RunStore(tmp_path / "runs.db")
    run = store.record(policy, evidence)
    assert run["report"]["verdict"] == "fail"
    assert store.get(run["id"])["report"] == run["report"]


def test_invalid_evidence_is_not_recorded(tmp_path, inputs):
    policy, evidence = inputs
    del evidence["provenance"]
    store = RunStore(tmp_path / "runs.db")
    with pytest.raises(EvidenceError):
        store.record(policy, evidence)
    assert not store.path.exists()


def test_lineage_comparison_and_changed_policy(tmp_path, inputs):
    policy, evidence = inputs
    store = RunStore(tmp_path / "runs.db")
    baseline = store.record(policy, evidence)
    evidence["metrics"]["candidate"]["auc"] += 0.01
    evidence["metrics"]["new_metric"] = 12
    candidate = store.record(policy, evidence, parent_id=baseline["id"])
    comparison = store.compare(baseline["id"], candidate["id"])
    assert comparison["same_policy"] is True
    auc = next(m for m in comparison["metrics"] if m["path"] == "metrics.candidate.auc")
    assert auc["delta"] == pytest.approx(0.01)
    missing = next(m for m in comparison["metrics"] if m["path"] == "metrics.new_metric")
    assert missing["baseline"] is None and missing["delta"] is None
    changed = replace(policy, checks=(replace(policy.checks[0], description="changed"),
                                     *policy.checks[1:]))
    other = store.record(changed, evidence)
    assert store.compare(candidate["id"], other["id"])["same_policy"] is False


def test_cross_project_and_unknown_parents_do_not_save(tmp_path, inputs):
    policy, evidence = inputs
    store = RunStore(tmp_path / "runs.db")
    first = store.record(policy, evidence)
    with pytest.raises(WorkspaceError, match="same project"):
        store.record(replace(policy, project="another"), evidence, parent_id=first["id"])
    with pytest.raises(WorkspaceError, match="not found"):
        store.record(policy, evidence, parent_id="missing")
    second = store.record(replace(policy, project="another"), evidence)
    with pytest.raises(WorkspaceError, match="same project"):
        store.compare(first["id"], second["id"])
    assert len(store.list()) == 2
    assert len(store.list(project="another")) == 1


def test_read_does_not_create_missing_store_and_bad_version_fails(tmp_path):
    store = RunStore(tmp_path / "missing.db")
    with pytest.raises(WorkspaceError):
        store.list()
    assert not store.path.exists()
    with sqlite3.connect(store.path) as conn:
        conn.execute("PRAGMA user_version = 999")
    with pytest.raises(WorkspaceError, match="unsupported workspace version"):
        store.list()


def test_changed_snapshot_is_rejected(tmp_path, inputs):
    policy, evidence = inputs
    store = RunStore(tmp_path / "runs.db")
    run = store.record(policy, evidence)
    run["report"]["verdict"] = "pass"
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE runs SET document = ?", (json.dumps(run),))
    with pytest.raises(WorkspaceError, match="digest mismatch"):
        store.get(run["id"])


def test_limit_and_actor_validation(tmp_path, inputs):
    policy, evidence = inputs
    store = RunStore(tmp_path / "runs.db")
    with pytest.raises(WorkspaceError, match="actor"):
        store.record(policy, evidence, actor=" ")
    for limit in (0, -1, 1001):
        with pytest.raises(WorkspaceError, match="limit"):
            store.list(limit=limit)


def test_cli_roundtrip_preserves_report_contract(tmp_path, capsys):
    db = tmp_path / "runs.db"
    code = main(["evaluate", "--policy", str(ROOT / "examples/recommendation/policy.yml"),
                 "--evidence", str(ROOT / "examples/recommendation/evidence.json"),
                 "--store", str(db), "--actor", "agent:test"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert "id" not in report
    assert main(["runs", "list", "--store", str(db)]) == 0
    run = json.loads(capsys.readouterr().out)[0]
    assert main(["runs", "show", run["id"], "--store", str(db)]) == 0
    assert json.loads(capsys.readouterr().out)["report"] == report
    assert main(["runs", "compare", run["id"], run["id"], "--store", str(db)]) == 0
    assert json.loads(capsys.readouterr().out)["same_policy"] is True
    html = tmp_path / "workspace.html"
    assert main(["workspace", "--store", str(db), "--output", str(html)]) == 0
    assert "Zanshin Proof" in html.read_text()
    assert main(["workspace", "--store", str(db), "--output", str(db)]) == 2
    assert len(RunStore(db).list()) == 1


def test_cli_errors_are_machine_safe(tmp_path, capsys):
    assert main(["runs", "show", "unknown", "--store", str(tmp_path / "absent")]) == 2
    assert capsys.readouterr().out == ""
    assert main(["evaluate", "--policy", "missing", "--evidence", "missing",
                 "--actor", "agent:test"]) == 2
    assert "require --store" in capsys.readouterr().err
