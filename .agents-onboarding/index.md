# Use Zanshin Proof with a coding agent

Proof evaluates observed ML evidence against an explicit release policy. It also saves and
compares evaluation snapshots and exports a visual review workspace. It does not train models,
deploy models, authenticate actors, or approve releases.

Start by reading the repository's `AGENTS.md`, `README.md`, and `docs/agent-workspace.md`.
Identify the user's model, source data, existing release policy, and evidence collector. If those
are missing, explain the gap. Use examples only as explicitly synthetic demonstrations.

## A working sequence

1. Run `uv sync --extra dev --locked` in a checkout of this repository.
2. Inspect `uv run zanshin-proof runs list --store .proof/runs.db` if a workspace exists.
3. Evaluate the user's evidence with their policy:

   ```bash
   uv run zanshin-proof evaluate \
     --policy PATH_TO_POLICY --evidence PATH_TO_EVIDENCE \
     --store .proof/runs.db --actor agent:YOUR_AGENT
   ```

4. Use the saved workspace run ID from stderr or `runs list`. Add `--parent RUN_ID` when
   evaluating a successor. IDs from the external training system are different identifiers.
5. Inspect `runs show RUN_ID --store .proof/runs.db`. Compare with
   `runs compare BASELINE_ID CANDIDATE_ID --store .proof/runs.db`.
6. Export `uv run zanshin-proof workspace --store .proof/runs.db` for human review.
7. Report the actual verdict, failed required checks, policy changes, and provenance limitations.

Exit `0` from `evaluate` means pass or warn, `1` means blocked, and `2` means invalid input or an
operation failure. Read commands return `0` for successful retrieval, regardless of the saved
verdict. Inspect the report's verdict. A passing policy is not human approval.

Never fabricate provenance, relabel synthetic evidence as measured performance, weaken required
checks to make a release pass, or treat a self-reported actor label as authenticated approval.
Exported HTML contains full evidence; do not publish or upload it without the user's instruction.

For a quick demonstration use `uv run python examples/workspace/make_demo.py`. Tell the user
that it uses synthetic evidence and does not execute model training.
