# Zanshin Proof

Evidence gates for calibrated AI decisions.

Zanshin Proof helps teams evaluate and release probabilistic decision systems, including
models trained with Reinforcement Learning for Calibrated Decisions (RLCD). It checks
observed facts and metrics against an explicit release policy. It gives
humans a compact evidence packet and gives CI a deterministic decision: pass, warn, or block.
Agents can help create code and collect evidence, but they do not approve their own work.

## Where Proof fits

Use Proof to gate a classifier, model router, or agent decision layer on evidence of
calibration, decision quality, automation coverage, and latency. Models supply predictions;
collectors supply observed labels; Proof computes metrics and applies explicit policy.

Proof is an evaluation and release-gating tool for RLCD-based systems. It does not train
RLCD models or provide a live Jev integration. Binary labeled outputs can be evaluated
directly; precomputed ML evidence is also supported.
Existing ML release policies remain supported.

See [Proof for calibrated decisions](docs/calibrated-decisions.md) for the evidence contract,
Jev and LangChain context, limitations, and integration roadmap.

## First working slice

The repository currently supports:

- Versioned YAML release policies
- Required and optional checks
- Boolean assertions, regression tolerances, and numeric thresholds
- Binary decision metrics: Brier score, top-label ECE, accuracy, selective error, coverage
- Optional paired baseline metrics, latency p95, and inspectable calibration bins
- Machine-readable JSON reports
- CI-safe exit codes
- A calibrated-decision policy with a runnable, explicitly synthetic demonstration
- A recommendation-model example
- Draft 2020-12 JSON Schemas for policies, evidence, and reports
- Required provenance binding evidence to code, model, run, source, and collection time

## Try it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```bash
uv sync --extra dev

uv run zanshin-proof evaluate \
  --policy examples/recommendation/policy.yml \
  --evidence examples/recommendation/evidence.json \
  --output proof-report.json
```

The example passes its required gates and surfaces catalog coverage as a warning. The command
returns `0` for `pass` or `warn`, `1` when a required check blocks release, and `2` for invalid
policy or evidence input.

Use `uv run pytest`, `uv run ruff check .`, and `uv build` for verification and packaging.

## Calibrated-decision demonstration

```bash
uv run python examples/calibrated-decisions/make_demo.py --decisions > /tmp/decisions.json
uv run zanshin-proof evaluate \
  --policy examples/calibrated-decisions/policy.yml \
  --decisions /tmp/decisions.json \
  --evidence-output /tmp/decision-evidence.json \
  --output /tmp/decision-report.json
```

This exercises required calibration, Brier score, accuracy regression, selective error,
coverage, sample count, and latency gates. Proof computes the metrics from synthetic
labeled records; this is not a Jev benchmark or release evidence. See the
[input contract and metric definitions](docs/decision-records.md).

## Policy example

```yaml
version: 1
project: recommendation-ranking
checks:
  - id: auc-regression
    type: metric_regression
    candidate: metrics.candidate.auc
    baseline: metrics.baseline.auc
    tolerance: 0.005

  - id: calibration-error
    type: max_value
    path: metrics.candidate.ece
    maximum: 0.03
```

## Design principles

- Explicit intent before execution
- Deterministic gates over agent self-assessment
- Independent evidence with provenance
- Required failures cannot be explained away
- Human ownership of promotion and approval
- Durable architecture documentation instead of disposable agent notes

See [docs/architecture.md](docs/architecture.md) for system boundaries and planned integrations.

## Evidence provenance

Every evidence document must identify:

- The complete Git commit SHA evaluated
- The model name and version
- The originating run system and run ID
- The collector and collection timestamp
- At least one versioned source table, dataset, file, API, or manual input

This provenance is validated before any checks run and is copied unchanged into the report. The
schemas are packaged under `src/zanshin_proof/schemas/` and enforced at runtime.

## Near-term roadmap

1. Multiclass metrics, evaluation slices, and uncertainty bounds
2. Optional Jev and LangChain evidence collectors
3. Signed evidence bundles and GitHub pull-request checks
4. MLflow and Databricks provenance collectors
5. Human approval workflow and review UI
