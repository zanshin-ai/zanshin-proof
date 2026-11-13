"""Local evaluation history for people and coding agents.

Snapshots are append-only through this API. They are not signed attestations, approvals,
or a model registry; evidence provenance remains supplied by the collector.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from zanshin_proof.evaluator import evaluate
from zanshin_proof.models import Policy
from zanshin_proof.schema import validate_document

DEFAULT_STORE = ".proof/runs.db"


class WorkspaceError(ValueError):
    """An invalid or unavailable workspace operation."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def policy_snapshot(policy: Policy) -> dict[str, Any]:
    return {
        "version": policy.version,
        "project": policy.project,
        "checks": [
            {
                **check.config,
                "id": check.id,
                "type": check.type,
                "required": check.required,
                "description": check.description,
            }
            for check in policy.checks
        ],
    }


def _metrics(value: dict[str, Any], prefix: str = "metrics") -> dict[str, float]:
    result: dict[str, float] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}"
        if isinstance(item, dict):
            result.update(_metrics(item, path))
        elif isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item):
            result[path] = item
    return result


class RunStore:
    """A versioned SQLite store; reads never create a missing database."""

    def __init__(self, path: str | Path = DEFAULT_STORE):
        self.path = Path(path)

    def _connect(self, *, write: bool = False) -> sqlite3.Connection:
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=10)
        else:
            conn = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in ({0, 1} if write else {1}):
                raise WorkspaceError(f"unsupported workspace version: {version}")
            if write and version == 0:
                conn.execute(
                    "CREATE TABLE runs (id TEXT PRIMARY KEY, project TEXT NOT NULL, "
                    "recorded_at TEXT NOT NULL, document TEXT NOT NULL)"
                )
                conn.execute("CREATE INDEX runs_project ON runs(project, recorded_at)")
                conn.execute("PRAGMA user_version = 1")
                conn.commit()
            return conn
        except Exception:
            conn.close()
            raise

    @staticmethod
    def _read(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT document FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise WorkspaceError(f"run not found: {run_id}")
        document = json.loads(row[0])
        for key in ("policy", "evidence", "report"):
            if _digest(document[key]) != document["digests"][key]:
                raise WorkspaceError(f"snapshot digest mismatch: {run_id} ({key})")
        return document

    def record(
        self, policy: Policy, evidence: dict[str, Any], *,
        actor: str = "unspecified", parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate and save a snapshot, including blocked runs. Never accept a caller's verdict."""
        if not actor.strip() or len(actor) > 200:
            raise WorkspaceError("actor must contain 1–200 characters")
        report = evaluate(policy, evidence).to_dict()
        snapshot = policy_snapshot(policy)
        validate_document(snapshot, "policy")
        validate_document(report, "report")
        document = {
            "version": 1,
            "id": uuid4().hex,
            "project": policy.project,
            "recorded_at": datetime.now(UTC).isoformat(),
            "actor": actor.strip(),
            "parent_id": parent_id,
            "policy": snapshot,
            "evidence": evidence,
            "report": report,
            "digests": {"policy": _digest(snapshot), "evidence": _digest(evidence),
                        "report": _digest(report)},
        }
        # Serialize before opening the DB: non-JSON/nonfinite input must not leave a run behind.
        serialized = _json(document)
        try:
            with closing(self._connect(write=True)) as conn, conn:
                if parent_id and self._read(conn, parent_id)["project"] != policy.project:
                    raise WorkspaceError("parent run must belong to the same project")
                conn.execute("INSERT INTO runs VALUES (?, ?, ?, ?)",
                             (document["id"], policy.project, document["recorded_at"], serialized))
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise WorkspaceError(f"could not record run: {exc}") from exc
        return json.loads(serialized)

    def get(self, run_id: str) -> dict[str, Any]:
        try:
            with closing(self._connect()) as conn:
                return self._read(conn, run_id)
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise WorkspaceError(f"could not read run: {exc}") from exc

    def list(self, *, project: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise WorkspaceError("limit must be between 1 and 1000")
        try:
            with closing(self._connect()) as conn:
                query = "SELECT id FROM runs"
                params: list[Any] = []
                if project is not None:
                    query += " WHERE project = ?"
                    params.append(project)
                query += " ORDER BY recorded_at DESC, id DESC LIMIT ?"
                params.append(limit)
                return [self._read(conn, row[0]) for row in conn.execute(query, params).fetchall()]
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise WorkspaceError(f"could not list runs: {exc}") from exc

    def compare(self, baseline_id: str, candidate_id: str) -> dict[str, Any]:
        baseline, candidate = self.get(baseline_id), self.get(candidate_id)
        if baseline["project"] != candidate["project"]:
            raise WorkspaceError("comparison requires two runs from the same project")
        left, right = (_metrics(run["evidence"]["metrics"]) for run in (baseline, candidate))
        return {
            "project": candidate["project"],
            "baseline_id": baseline_id,
            "candidate_id": candidate_id,
            "same_policy": baseline["digests"]["policy"] == candidate["digests"]["policy"],
            "baseline_verdict": baseline["report"]["verdict"],
            "candidate_verdict": candidate["report"]["verdict"],
            "metrics": [
                {"path": key, "baseline": left.get(key), "candidate": right.get(key),
                 "delta": right[key] - left[key] if key in left and key in right else None}
                for key in sorted(left.keys() | right.keys())
            ],
        }
