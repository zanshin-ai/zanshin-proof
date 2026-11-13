# An evaluation workspace for people and agents

Zanshin Proof now joins evaluation, persistent run history, comparison, and visual review.
It builds on Proof's deterministic policy engine. A passing gate supplies evidence for review;
it does not grant human approval.

## Start with the synthetic demo

```bash
uv sync --extra dev --locked
uv run python examples/workspace/make_demo.py
```

Open `proof-workspace.html` in your browser. It contains three explicitly synthetic model
versions, including a blocked regression. The script uses the existing recommendation fixture;
the metrics demonstrate the workflow, not measured model performance. It runs no training.
Repeated invocations append three more runs to `.proof/demo.db`.

## Save the sample evaluation

```bash
uv run zanshin-proof evaluate \
  --policy examples/recommendation/policy.yml \
  --evidence examples/recommendation/evidence.json \
  --store .proof/runs.db \
  --actor agent:codex \
  --output /tmp/proof-report.json
```

The JSON report on stdout and existing exit codes stay unchanged. The workspace run ID is
printed on stderr. `--decisions` can be used instead of `--evidence`. A run with failing required
checks is saved and still returns exit code `1`. Invalid evidence returns `2` without saving a run.
If report-file writing fails after a run is saved, the run remains in history and the CLI returns `2`.

This checked-in recommendation fixture is synthetic and returns `warn` because catalog coverage
is below its optional threshold. Replace the policy and evidence paths with your own inputs for
a real evaluation; the command does not collect predictions or establish the fixture's facts.

Each run snapshots its full normalized policy, evidence, and computed report, with SHA-256
digests and the actual recording time. Original collector provenance is retained. Actor labels
are self-reported attribution, not authenticated identities. Recording time is separate from
evidence collection time. Hashes detect accidental modification, not malicious rewriting of a
local database; this is not a signed or tamper-proof audit store.

## Give your coding agent the same workflow

```bash
uv run zanshin-proof runs list --store .proof/runs.db
uv run zanshin-proof runs show RUN_ID --store .proof/runs.db
uv run zanshin-proof runs compare BASELINE_ID CANDIDATE_ID --store .proof/runs.db
```

Run IDs are local workspace IDs from `runs list`, distinct from the originating run system's ID.
Use `--parent RUN_ID` on a subsequent `evaluate --store ...` to record lineage. The parent must
exist and belong to the same project. Run history is append-only through the public API.

Comparisons return candidate-minus-baseline deltas for every numeric metric, including nested
metrics. Missing values have a null delta; a delta alone does not establish improvement. Runs
must share a project. `same_policy: false` makes policy changes explicit; comparison never grants
approval or overrides a verdict. Listing and comparison exit `0` when retrieval succeeds, even
when a saved verdict is blocked; automation must inspect the saved report, or run `evaluate`.

Selecting a baseline run in the comparison view changes the displayed deltas. A saved regression
gate uses the baseline metric already present in that run's evidence; comparison does not replace
it or re-evaluate the policy. In the synthetic demo, that evidence baseline AUC is `0.812`, so the
`0.005` tolerance gives a policy floor of `0.807`, even when comparing against another saved run.

The default store for read/export commands is `.proof/runs.db`. Put `--store` after the run
subcommand as shown above. `runs list` accepts `--project` and `--limit` (1–1000, default 100).
Missing or unsupported databases return `2`; read commands never create an empty store.

See [agent onboarding](../.agents-onboarding/index.md) for a copyable operating workflow.

## Review in a browser

```bash
uv run zanshin-proof workspace --store .proof/runs.db --output proof-workspace.html
```

The self-contained HTML has project and verdict filters, model/run search, metric comparisons,
policy-check detail, provenance, policy/evidence snapshots, and report downloads. It uses no
external assets or network requests. The export contains the 100 most recent runs by default;
use `--limit` (up to 1000) or `--project` to control its contents. Re-export to see new runs.

The HTML embeds full evidence and provenance. Review its contents before sharing; exports are
not access-controlled. `.proof/` and the default HTML export are ignored by Git. Store your
database on durable local storage and back it up through your normal process if needed.

## Product direction

The current workspace concentrates on evaluation history and release evidence.

| Capability | Current implementation | Next boundary |
| --- | --- | --- |
| Agent workflow | CLI JSON, actor labels, parent runs, onboarding guide | MCP tools and authenticated actors |
| Experiment history | Evaluated metrics, policy/evidence/report snapshots in SQLite | External tracker collectors and training-run metadata |
| Comparison | Numeric deltas, policy fingerprints, inspectable gates | Evaluation slices and multiclass support |
| Review | Offline HTML workspace, evidence and report inspection | Authenticated review app and approval enforcement |
| Training | Models are trained outside Proof | Isolated, budgeted execution and experiment orchestration |
| Deployment | CI-safe gate verdicts | Registry and deployment adapters |
| Monitoring | None | Production evidence collection and drift checks |

The local store is deliberately a single-user boundary. Multi-user hosting needs authenticated
access, storage migrations, concurrency/load limits, and separate approval identities before it
can make stronger lifecycle or audit claims.
