# Architecture

## Purpose

Zanshin Proof converts explicit release policy and observed calibrated-decision or ML evidence
into a deterministic, auditable verdict. It computes metrics from supplied binary decision records and does not replace human approval.

## Current boundary

Evaluation has five parts:

1. A versioned YAML policy describes required and optional checks.
2. Input is either a JSON evidence document or versioned labeled binary decision records.
   The decision adapter validates records and computes metrics into evidence v1.
3. Draft 2020-12 JSON Schemas validate policy and evidence before checks run.
4. A deterministic engine evaluates each check without model judgment.
5. The CLI validates and emits a JSON report with the original provenance attached.

An optional workspace adds SQLite snapshots of the normalized policy, evidence, and computed
report. Evaluation still uses the same engine. Each run gets a local workspace ID, actual
recording time, self-reported actor, optional same-project parent, and snapshot SHA-256 digests.
Reads verify those digests and never create a missing database. Public write operations append;
there is no edit, delete, approve, promote, train, or deploy operation.

CLI inspection and comparison return JSON. An offline HTML export supplies a visual review
workspace, built from the stored records with no external assets or runtime server. It is a
snapshot, not a live multi-user app. See [the workspace guide](agent-workspace.md).

For `evaluate`, exit code `0` means pass or warn, `1` means a required check failed or errored,
and `2` means invalid input or an operation failure. Read and export commands return `0` on
successful retrieval/export, regardless of saved verdicts, and `2` on an operation failure.

## Trust model

The evaluator trusts neither prose nor an agent's assertion of success. Evidence is rejected
unless it identifies a full Git commit SHA, model name and version, originating run, collector,
collection time, and at least one versioned source. Passing schema validation proves that these
claims are present and well-formed; it does not prove that they are true. Future collectors and
signatures will establish authenticity and bind the claims to their producing systems.

The decision adapter and report copy supplied provenance rather than reconstructing or enriching
it. Computed evidence records the method, settings, and canonical input hash under
`metrics.computation`; it does not fabricate collector or model identifiers. This preserves the boundary between observed input and evaluator output.

## Planned seams

- Evidence collectors for GitHub, Databricks, and MLflow
- Schema migrations beyond version 1
- Approval identities and separation-of-duties rules
- Signed evidence bundles and immutable audit storage
- Pull-request check reporting and authenticated review workflows
- Training/external tracker adapters, model registry and deployment integration, monitoring

## Calibrated decision systems

The same policy engine can gate RLCD-based decision systems on computed or externally supplied
calibration, selective error, coverage, and latency metrics. No model participates in
policy evaluation. The binary decision adapter is a separate deterministic component; live provider collectors
remain future work. The existing evidence, report, and policy schemas are unchanged. See the
[decision evidence contract](calibrated-decisions.md) for definitions and limitations.

