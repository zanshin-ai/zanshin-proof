# Evaluate binary decision outputs

`zanshin-proof evaluate --decisions decisions.json --policy policy.yml` computes
metrics from labeled binary outputs, then applies the same deterministic policy engine
used for precomputed evidence. No model calls or additional dependencies are required.
This measures calibration; it does not recalibrate probabilities or train a model.

## Input contract

The packaged [decisions v1 schema](../src/zanshin_proof/schemas/decisions.schema.json)
is additive. Existing evidence, policy, and report v1 formats remain unchanged.
A decision document contains:

- `version`: `1`.
- `provenance`: the existing evidence provenance object, supplied by the collector.
- `facts`: externally established facts such as held-out evaluation and output-contract checks.
  Proof copies them; successfully parsing records does not establish these claims.
- `evaluation`: required `bin_count` (integer 1–1000) and `automation_threshold` (0.5–1).
- `records`: a nonempty array of uniquely identified, equally weighted labeled decisions.

Each record has the following form (optional fields shown):

```json
{
  "id": "ticket-123",
  "probability": 0.9,
  "label": 1,
  "baseline_probability": 0.8,
  "latency_ms": 125
}
```

`probability` is P(label = 1), not the confidence of whichever class was selected.
Labels are numeric 0 or 1. Booleans, strings, missing labels, duplicate IDs, unknown
record fields, nonfinite numbers, and probabilities outside [0, 1] are rejected.
An absent outcome is not a negative label. The records must refer to one frozen binary
question / outcome definition; do not pool unrelated questions into one metric.

Optional baseline probabilities and nonnegative candidate latency measurements must each
be present on every record or on none. Partial coverage is rejected rather than silently
changing the evaluated population. A baseline probability is paired with the same label
on its record. Identify the baseline model, question, dataset, and configuration through
versioned `provenance.sources` entries; the primary `provenance.model` is the candidate.
The v1 adapter does not independently verify these identities.

## Exact metric definitions

Let `p` be the positive-class probability and `y` its observed label. The predicted class
is 1 when `p >= 0.5` (ties choose 1), otherwise 0. Confidence is `max(p, 1-p)`.

| Metric under `metrics.candidate` | Definition |
| --- | --- |
| `sample_count` | Number of records |
| `accuracy` | Fraction with predicted class equal to label |
| `brier` | Mean `(p-y)^2`, binary scale [0, 1], lower is better |
| `ece` | Top-label expected calibration error, as defined below |
| `automated_count` | Number with confidence >= the automation threshold |
| `coverage` | Automated count / sample count |
| `selective_error` | Incorrect automated predictions / automated count; omitted when count is zero |
| `p95_latency_ms` | Sorted latency at one-based rank `ceil(0.95 * n)`; omitted without latency input |
| `calibration_bins` | Bin bounds, count, mean confidence, and accuracy; empty means/accuracies are null |

ECE divides [0, 1] into `bin_count` equal-width bins. Bins are left-closed and right-open,
except the last includes 1. Each record is placed by `min(floor(confidence * bin_count),
bin_count - 1)`. ECE is the sum over nonempty bins of
`(bin_count_observed / sample_count) * abs(mean_confidence - accuracy)`.
This is **top-label ECE**, not positive-class probability ECE. Empty bins contribute zero.
The returned histogram makes the estimate inspectable; binning and small samples can hide
errors. Brier score captures more than calibration alone, as explained in the
[scikit-learn calibration guide](https://scikit-learn.org/1.8/modules/calibration.html).

The same probability metrics are computed under `metrics.baseline` when paired baseline
probabilities are present, using the same configuration and labels. Latency is candidate-only.
Automation is a deterministic simulation at the supplied confidence threshold, not a
measurement of a deployed router's actions. Freeze that threshold and binning before
examining held-out results. Policy can also gate `metrics.computation.automation_threshold`
or `bin_count` using existing numeric checks to enforce the expected configuration.

## Computed evidence and reports

```bash
uv run python examples/calibrated-decisions/make_demo.py --decisions > /tmp/decisions.json
uv run zanshin-proof evaluate \
  --decisions /tmp/decisions.json \
  --policy examples/calibrated-decisions/policy.yml \
  --evidence-output /tmp/computed-evidence.json \
  --output /tmp/report.json
```

The example uses synthetic records and makes no provider call. All required gates pass.
Without `--decisions`, the example generator retains its earlier precomputed fixture mode.

`--evidence` and `--decisions` are mutually exclusive. `--evidence-output` is optional and
requires `--decisions`; it saves computed metrics and calibration bins as ordinary evidence
v1, which can be passed back into `evaluate --evidence`. The report format is unchanged:
it contains policy check observations and provenance. Save computed evidence to retain
metrics that the policy does not reference.

Input provenance and facts are copied unchanged. `metrics.computation` records the
`binary-decisions-v1` method, bin count, threshold, and SHA-256 of the input serialized with
Python `json.dumps(sort_keys=True, separators=(",", ":"), allow_nan=False)` and UTF-8.
This is a reproducibility fingerprint, not a signature; array order and numeric representation
can change it. The collector remains responsible for real model and dataset provenance.

Exit codes remain 0 for pass/warn, 1 for a required failed or missing metric, and 2 for
invalid input or an output-write failure. Required baseline or latency gates fail if those
optional inputs were absent. No automated decisions means zero coverage and an omitted
selective error, so required risk checks block. Invalid input produces no new report or
evidence; previously existing output files are not removed. Use fresh output paths in CI.

## Current limits

Binary, unweighted, fully labeled records only. This implementation does not provide
multiclass scoring, slice analysis, confidence intervals, provider adapters, or signed
provenance. Low aggregate ECE is not a guarantee of correctness or safety. Keep sample-size,
automated-count, coverage, and task-specific error checks in the release policy.
