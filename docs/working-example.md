# From labeled decisions to a release verdict

This walkthrough uses the binary decision computation already available on `main`.
Commands assume a POSIX shell (macOS, Linux, or WSL), Python 3.11+, and
[uv](https://docs.astral.sh/uv/). The sample is deliberately synthetic and calls no model API.

## 1. Set up and generate labeled records

```bash
git clone https://github.com/zanshin-ai/zanshin-proof.git
cd zanshin-proof
uv sync --extra dev --locked
uv run python examples/calibrated-decisions/make_demo.py --decisions > /tmp/decisions.json
```

If you already have the current checkout, start at `uv sync`. The generator emits 100
records, each predicting the positive class with probability 0.99; 99 labels are positive
and one is negative. It also supplies paired baseline probabilities and synthetic latencies.
Provenance identifies this local fixture-generation run. No credentials are needed.

## 2. Compute metrics and apply the policy

```bash
uv run zanshin-proof evaluate \
  --policy examples/calibrated-decisions/policy.yml \
  --decisions /tmp/decisions.json \
  --evidence-output /tmp/decision-evidence.json \
  --output /tmp/decision-report.json
```

The terminal prints the report and exits with `0`. The report's verdict is `pass`, with
nine passing checks. `/tmp/decision-evidence.json` contains all computed metrics and bins;
`/tmp/decision-report.json` contains the policy results and supplied provenance.

| Candidate metric | Expected value |
| --- | --- |
| Sample count | 100 |
| Accuracy | 0.99 |
| Binary Brier score | Approximately 0.0099 |
| Top-label ECE | 0 |
| Automated count | 100 |
| Coverage | 1 |
| Selective error | 0.01 |
| p95 latency | 180 ms |

The paired baseline accuracy is also 0.99, while its Brier score is approximately 0.0115
and ECE is approximately 0.04. This illustrates why equal accuracy need not mean equal
probability quality. The example policy gates candidate calibration and accuracy regression;
it does not gate the baseline Brier score or ECE.

Inspect both files using a JSON viewer, or:

```bash
uv run python -m json.tool /tmp/decision-evidence.json
uv run python -m json.tool /tmp/decision-report.json
```

## 3. Observe a blocked release

Create a separate synthetic failure variant without changing the policy:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

source = json.loads(Path('/tmp/decisions.json').read_text())
for record in source['records']:
    record['probability'] = 0.01
Path('/tmp/decisions-failing.json').write_text(json.dumps(source, indent=2))
PY

uv run zanshin-proof evaluate \
  --policy examples/calibrated-decisions/policy.yml \
  --decisions /tmp/decisions-failing.json \
  --evidence-output /tmp/failing-evidence.json \
  --output /tmp/failing-report.json
```

Expected: verdict `fail`, exit code **1**, and four failed required checks: calibration
error, Brier score, accuracy regression, and automated-decision error. The candidate is
now confidently wrong on 99 of 100 records. Coverage and latency still pass. In CI or a
shell using `set -e`, exit code 1 stops subsequent commands; that is the intended behavior.

This edited document remains a synthetic teaching fixture. It retains the original fixture
run's provenance; the computed input fingerprint changes. It is not fresh release evidence.

## 4. Reuse the computed evidence

```bash
uv run zanshin-proof evaluate \
  --policy examples/calibrated-decisions/policy.yml \
  --evidence /tmp/decision-evidence.json \
  --output /tmp/replayed-report.json
```

This reproduces the original passing verdict without recomputing metrics. Use `--decisions`
for raw labeled outputs and `--evidence` for already computed evidence; do not pass both.

## 5. Replace the fixture with your outputs

Export a complete document using the [decision-record schema and field definitions](decision-records.md):

- Supply your actual code revision, model version, collection time, collector, run, and versioned
  source artifacts. Identify any baseline model in the source artifacts as well.
- Use one binary question and its independent observed labels. `probability` means P(label=1),
  not the selected class's confidence. Missing outcomes are not negative labels.
- Include unique record IDs. Baseline probabilities and latency are optional, but each must
  cover all records or none. The example policy requires both; missing metrics block it.
- Freeze the bin count, automation threshold, and release policy before evaluating held-out data.
- Establish facts such as `held_out_evaluation` and `typed_output_valid` independently.
  Do not copy the demo's `true` values or its model identity into production evidence.

Then run the same command with your document and policy paths. Choose thresholds and
sample sizes appropriate to your workflow; the example's values are illustrative. The
computed coverage simulates a confidence threshold, not a deployed router's action log.
Zero automated decisions leave selective error undefined and block a required error gate.
Multiclass scoring, uncertainty intervals, and live provider collection are not implemented.
