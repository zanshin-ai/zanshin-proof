# README visuals

`proof-workspace.webp` and `proof-workflow.gif` are captures of the actual exported workspace,
using the three-run synthetic recommendation example. No production model performance is shown.
The animation is a twelve-second sequence of three captured UI states with explanatory captions.
It repeats, with a static screenshot linked alongside it in the main README.

`proof-concept.svg` explains how evidence and a versioned release policy produce deterministic
verdicts. Human review is a release-owner responsibility; the diagram does not claim that Proof
implements authenticated approvals or deployment.

## Reproduce captures

From the repository root, with Python 3.11+ and uv installed:

```bash
uv sync --extra dev --locked
uv run --with playwright --with Pillow python -m playwright install --with-deps chromium
uv run --with playwright --with Pillow python examples/workspace/capture_readme.py
```

The capture script runs `make_demo.py` into a temporary database, opens the actual exported HTML
over a temporary loopback HTTP server in an isolated browser, and performs the visible actions.
It checks the three runs, blocked comparison, failed-check details, JavaScript errors, and phone
layout before creating assets in `/tmp/proof-readme-assets/`. Copy reviewed outputs here.
The optional packages are used only for documentation capture, not runtime dependencies.

The `README visuals` workflow reproduces this process and uploads its assets. `--emit-base64`
also emits the synthetic-only image bytes for retrieval through the GitHub log connector when
artifact materialization is unavailable; leave it off for ordinary local captures.
