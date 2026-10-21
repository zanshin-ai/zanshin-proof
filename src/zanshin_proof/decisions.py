"""Deterministic binary decision metrics, separate from policy evaluation."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

from zanshin_proof.evaluator import EvidenceError
from zanshin_proof.schema import DocumentValidationError, validate_document


def _finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise EvidenceError("decision documents must contain only finite numbers")
    if isinstance(value, dict):
        for item in value.values():
            _finite(item)
    elif isinstance(value, list):
        for item in value:
            _finite(item)


def _metrics(records: list[dict], field: str, bins: int, threshold: float) -> dict:
    n = len(records)
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    correct = automated = errors = 0
    losses = []
    for record in records:
        p, label = record[field], record["label"]
        confidence = max(p, 1 - p)
        hit = int(p >= 0.5) == label
        correct += hit
        losses.append((p - label) ** 2)
        buckets[min(int(confidence * bins), bins - 1)].append((confidence, hit))
        if confidence >= threshold:
            automated += 1
            errors += not hit
    histogram = []
    gaps = []
    for i, bucket in enumerate(buckets):
        count = len(bucket)
        mean = math.fsum(c for c, _ in bucket) / count if count else None
        accuracy = sum(hit for _, hit in bucket) / count if count else None
        histogram.append({
            "lower": i / bins, "upper": (i + 1) / bins, "count": count,
            "mean_confidence": mean, "accuracy": accuracy,
        })
        if count:
            gaps.append(count / n * abs(mean - accuracy))
    result = {
        "sample_count": n,
        "accuracy": correct / n,
        "brier": math.fsum(losses) / n,
        "ece": math.fsum(gaps),
        "automated_count": automated,
        "coverage": automated / n,
        "calibration_bins": histogram,
    }
    if automated:
        result["selective_error"] = errors / automated
    return result


def compute_evidence(document: dict[str, Any]) -> dict[str, Any]:
    """Validate decision v1 input and return evidence v1 without inventing provenance."""
    _finite(document)
    try:
        validate_document(document, "decisions")
    except DocumentValidationError as exc:
        raise EvidenceError(str(exc)) from exc
    records = document["records"]
    ids = [record["id"] for record in records]
    if len(set(ids)) != len(ids):
        raise EvidenceError("decision record IDs must be unique")
    for field in ("baseline_probability", "latency_ms"):
        count = sum(field in record for record in records)
        if count not in (0, len(records)):
            raise EvidenceError(f"{field} must be supplied for all records or none")
    config = document["evaluation"]
    bins, threshold = config["bin_count"], config["automation_threshold"]
    # JSON Schema accepts 10.0 as an integer; normalize it for range().
    bins = int(bins)
    candidate = _metrics(records, "probability", bins, threshold)
    if "latency_ms" in records[0]:
        latencies = sorted(record["latency_ms"] for record in records)
        candidate["p95_latency_ms"] = latencies[math.ceil(0.95 * len(latencies)) - 1]
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    metrics = {
        "candidate": candidate,
        "computation": {
            "method": "binary-decisions-v1",
            "input_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "bin_count": bins,
            "automation_threshold": threshold,
        },
    }
    if "baseline_probability" in records[0]:
        metrics["baseline"] = _metrics(records, "baseline_probability", bins, threshold)
    evidence = {
        "provenance": deepcopy(document["provenance"]),
        "facts": deepcopy(document["facts"]),
        "metrics": metrics,
    }
    validate_document(evidence, "evidence")
    return evidence
