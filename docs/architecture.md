# Architecture

## Purpose

Zanshin Proof converts explicit release policy and observed calibrated-decision or ML evidence
into a deterministic, auditable verdict. It does not generate evidence and it does not replace human approval.

## Current boundary

The first vertical slice has five parts:

1. A versioned YAML policy describes required and optional checks.
2. A JSON evidence document contains facts, metrics, and mandatory provenance.
3. Draft 2020-12 JSON Schemas validate policy and evidence before checks run.
4. A deterministic engine evaluates each check without model judgment.
5. The CLI validates and emits a JSON report with the original provenance attached.

Exit code `0` means the release is not blocked, `1` means required evidence failed, and `2`
means the input could not be safely interpreted.

## Trust model

The evaluator trusts neither prose nor an agent's assertion of success. Evidence is rejected
unless it identifies a full Git commit SHA, model name and version, originating run, collector,
collection time, and at least one versioned source. Passing schema validation proves that these
claims are present and well-formed; it does not prove that they are true. Future collectors and
signatures will establish authenticity and bind the claims to their producing systems.

The report copies provenance from the validated evidence rather than reconstructing or enriching
it. This preserves the boundary between observed input and evaluator output.

## Planned seams

- Evidence collectors for GitHub, Databricks, and MLflow
- Schema migrations beyond version 1
- Approval identities and separation-of-duties rules
- Signed evidence bundles and immutable audit storage
- Pull-request check reporting and a human review UI

## Calibrated decision systems

The same policy engine can gate RLCD-based decision systems on externally computed
calibration, selective error, coverage, and latency metrics. No model participates in
policy evaluation. Collectors and metric computation remain separate future components;
the current schemas and existing ML policies are unchanged. See the
[decision evidence contract](calibrated-decisions.md) for definitions and limitations.
