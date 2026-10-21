"""Command-line interface for Zanshin Proof."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from zanshin_proof.decisions import compute_evidence
from zanshin_proof.evaluator import EvidenceError, evaluate
from zanshin_proof.models import Status
from zanshin_proof.policy import PolicyError, load_policy
from zanshin_proof.schema import DocumentValidationError, validate_document


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.evidence_output and not args.decisions:
            raise EvidenceError("--evidence-output requires --decisions")
        paths = [args.policy, args.evidence or args.decisions, args.output, args.evidence_output]
        resolved = [Path(path).resolve() for path in paths if path]
        if len(set(resolved)) != len(resolved):
            raise EvidenceError("input and output paths must be distinct")
        policy = load_policy(args.policy)
        evidence = (
            compute_evidence(_load_evidence(args.decisions))
            if args.decisions else _load_evidence(args.evidence)
        )
        report = evaluate(policy, evidence)
    except (PolicyError, EvidenceError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    report_document = report.to_dict()
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
    return 0 if report.verdict in {Status.PASS, Status.WARN} else 1


if __name__ == "__main__":
    raise SystemExit(main())
