# Proof for calibrated decisions

Zanshin Proof is an evidence and release-gating tool for systems that make typed,
probabilistic decisions, including models trained with Reinforcement Learning for
Calibrated Decisions (RLCD). It evaluates supplied evidence; it does not implement
RLCD training, calculate calibration metrics, or call a model provider.

## Why this direction

[TypeSafe introduces RLCD](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
as its training method for calibrated decisions. Jev returns structured answers and
probabilities. [LangChain's harness article](https://www.langchain.com/blog/building-a-harness-with-jev)
shows how these decisions can support routing and tool-call checks.

Proof's role is to check evidence about that decision layer before a model or harness
change ships. A schema-valid answer can still be wrong. A confidence score is a
prediction to evaluate against outcomes, not proof of correctness or permission to act.
These articles motivate this use case; they do not specify a reproducible RLCD trainer.

## Workflow and boundaries

1. Define the question, allowed answers, outcome labels, and the workflow's error costs.
2. Freeze the candidate, baseline, question definitions, routing thresholds, and evaluation set.
3. An external evaluator collects probabilities, independent labels, decisions, and timing.
4. That evaluator calculates metrics and exports a version 1 evidence document.
5. Proof applies a versioned policy and emits a deterministic pass, warn, or fail report.
6. A human-owned release process decides promotion. Runtime code handles routing and abstention.

Proof currently implements step 5. It can gate evidence from Jev, other classifiers,
or conventional ML models without a provider dependency. It does not currently collect
Jev responses, intercept tool calls, enforce runtime abstention, or train models.

## Evidence contract for the example

The [example policy](../examples/calibrated-decisions/policy.yml) uses existing check
types and the existing evidence schema. Its thresholds illustrate a policy; choose and
validate your own before evaluating a candidate.

| Evidence path under `metrics.candidate` | External evaluator's definition |
| --- | --- |
| `sample_count` | Number of independently labeled held-out decisions |
| `accuracy` | Correct argmax decisions divided by all labeled decisions |
| `ece` | Top-label expected calibration error: bin-size-weighted absolute difference between mean confidence and accuracy; specify fixed bin edges |
| `brier` | Binary Brier score, mean `(p - y)^2`, where `p` predicts the positive class and `y` is 0 or 1 |
| `selective_error` | Incorrect automated decisions divided by all automated decisions at the frozen routing threshold |
| `coverage` | Automated decisions divided by all evaluated decisions at that same threshold |
| `p95_latency_ms` | 95th percentile of end-to-end decision latency in milliseconds; record environment and percentile convention |

`metrics.baseline.accuracy` must use the same held-out examples and label definition.
`facts.typed_output_valid` records independent output-contract validation;
`facts.held_out_evaluation` records evaluation-set separation from training and threshold tuning.
The example is binary; do not mix binary and multiclass Brier conventions.

Gate selective error together with coverage so abstaining on every decision cannot pass.
If no decisions are automated, selective error is undefined: omit it and let the required
check block. Do not substitute zero. Supply finite, valid metric values; the current
engine checks supplied values against policy thresholds, not their derivation or statistical validity.

Aggregate metrics are insufficient for production assurance. Add required checks for
critical slices, harmful false negatives, minimum automated sample counts, and uncertainty
bounds where appropriate. ECE depends on binning and sample size; a low point estimate
alone does not establish calibration. Freeze thresholds on a separate validation split.

## Run the synthetic policy demonstration

From the repository root, after `uv sync --extra dev`:

```bash
uv run python examples/calibrated-decisions/make_demo.py > /tmp/decision-evidence.json
uv run zanshin-proof evaluate \
  --policy examples/calibrated-decisions/policy.yml \
  --evidence /tmp/decision-evidence.json \
  --output /tmp/decision-report.json
```

The demonstration passes all required checks. Its facts and metrics are explicitly
synthetic constants, not measured performance, a real held-out evaluation, or a Jev
benchmark. The generator records the actual checkout HEAD, generation time, run UUID,
and source-file hash; the hash identifies the script even with uncommitted edits.
Provenance describes the fixture-generation run, not a model evaluation.

For a real release, replace the entire evidence document with independently collected
results and real provenance. Pin model versions, question schemas, label sources,
workflow code, threshold configuration, and dataset versions in the producing system;
reference those versioned artifacts in `provenance.sources`. Do not use a mutable
`latest` model alias as the only model identity. Schema validation checks presence and
shape, not authenticity or whether synthetic evidence is suitable for release.

## Next increments

- A versioned decision-record format for probabilities, labels, abstentions, and outcomes.
- Deterministic metric computation with documented binning, slices, and sample counts.
- Optional Jev / LangChain collectors preserving question definitions and model versions.
- Candidate-versus-baseline comparison of calibration, decision risk, cost, and latency.
- Signed evidence and CI reporting, followed by explicit human approval controls.

These are planned capabilities, not current integrations. RLCD training and reward design
remain outside the current project boundary.
