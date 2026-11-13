"""Command-line interface for Zanshin Proof."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from zanshin_proof.dashboard import render_workspace
from zanshin_proof.decisions import compute_evidence
from zanshin_proof.evaluator import EvidenceError, evaluate
from zanshin_proof.models import Status
from zanshin_proof.policy import PolicyError, load_policy
from zanshin_proof.schema import DocumentValidationError, validate_document
from zanshin_proof.workspace import DEFAULT_STORE, RunStore, WorkspaceError


def _load_evidence(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Could not load evidence {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError("evidence must be a JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zanshin-proof",
        description="Evaluate calibrated-decision and ML evidence against a release policy.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = subparsers.add_parser("evaluate", help="evaluate an evidence document")
    evaluate_parser.add_argument("--policy", required=True, help="path to policy YAML")
    inputs = evaluate_parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--evidence", help="path to evidence JSON")
    inputs.add_argument("--decisions", help="path to labeled binary decisions JSON")
    evaluate_parser.add_argument("--evidence-output", help="save metrics computed from --decisions")
    evaluate_parser.add_argument("--output", help="optional path for the JSON report")
    evaluate_parser.add_argument("--store", help="also save this evaluation in a SQLite workspace")
    evaluate_parser.add_argument("--actor", help="self-reported human or agent label; not approval")
    evaluate_parser.add_argument("--parent", help="workspace run ID that this run builds on")
    runs = subparsers.add_parser("runs", help="inspect and compare saved evaluations as JSON")
    actions = runs.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list", help="list recent run summaries")
    listing.add_argument("--project", help="filter by exact project name")
    listing.add_argument("--limit", type=int, default=100, help="1–1000, default 100")
    show = actions.add_parser("show", help="show a complete policy, evidence, and report snapshot")
    show.add_argument("run_id")
    compare = actions.add_parser("compare", help="compare runs; deltas are candidate − baseline")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    for action in (listing, show, compare):
        action.add_argument("--store", default=DEFAULT_STORE, help="SQLite workspace path")
    workspace = subparsers.add_parser("workspace", help="export a portable HTML review workspace")
    workspace.add_argument("--store", default=DEFAULT_STORE, help="SQLite workspace path")
    workspace.add_argument("--project", help="export only this project")
    workspace.add_argument("--limit", type=int, default=100, help="1–1000 recent runs, default 100")
    workspace.add_argument("--output", default="proof-workspace.html", help="HTML output path")
    return parser


def _workspace_command(args: argparse.Namespace) -> int:
    store = RunStore(args.store)
    try:
        if args.command == "workspace":
            if Path(args.output).resolve() == Path(args.store).resolve():
                raise WorkspaceError("workspace output must differ from the database path")
            runs = store.list(project=args.project, limit=args.limit)
            Path(args.output).write_text(render_workspace(runs), encoding="utf-8")
            result: Any = {"output": str(Path(args.output).resolve()), "runs": len(runs)}
        elif args.action == "show":
            result = store.get(args.run_id)
        elif args.action == "compare":
            result = store.compare(args.baseline, args.candidate)
        else:
            result = [
                {"id": run["id"], "project": run["project"], "actor": run["actor"],
                 "parent_id": run["parent_id"], "recorded_at": run["recorded_at"],
                 "verdict": run["report"]["verdict"],
                 "model": run["evidence"]["provenance"]["model"]}
                for run in store.list(project=args.project, limit=args.limit)
            ]
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (WorkspaceError, OSError, ValueError) as exc:
        print(f"workspace error: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "evaluate":
        return _workspace_command(args)
    try:
        if args.evidence_output and not args.decisions:
            raise EvidenceError("--evidence-output requires --decisions")
        if (args.actor is not None or args.parent is not None) and not args.store:
            raise EvidenceError("--actor and --parent require --store")
        paths = [args.policy, args.evidence or args.decisions, args.output,
                 args.evidence_output, args.store]
        resolved = [Path(path).resolve() for path in paths if path]
        if len(set(resolved)) != len(resolved):
            raise EvidenceError("input and output paths must be distinct")
        policy = load_policy(args.policy)
        evidence = (
            compute_evidence(_load_evidence(args.decisions))
            if args.decisions else _load_evidence(args.evidence)
        )
        if args.store:
            run = RunStore(args.store).record(
                policy, evidence, actor=args.actor if args.actor is not None else "unspecified",
                parent_id=args.parent,
            )
            report_document = run["report"]
            print(f"saved workspace run: {run['id']}", file=sys.stderr)
        else:
            report_document = evaluate(policy, evidence).to_dict()
    except (PolicyError, EvidenceError, WorkspaceError, DocumentValidationError, ValueError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        validate_document(report_document, "report")
    except DocumentValidationError as exc:
        print(f"internal report error: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report_document, indent=2, sort_keys=True)
    try:
        if args.evidence_output:
            Path(args.evidence_output).write_text(
                json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        if args.output:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"output error: {exc}", file=sys.stderr)
        return 2
    print(rendered)
    return 0 if report_document["verdict"] in {Status.PASS, Status.WARN} else 1


if __name__ == "__main__":
    raise SystemExit(main())

