"""Create a clearly synthetic three-run workspace. Does not train or deploy models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from zanshin_proof.dashboard import render_workspace
from zanshin_proof.policy import load_policy
from zanshin_proof.workspace import RunStore

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default=".proof/demo.db")
    parser.add_argument("--output", default="proof-workspace.html")
    args = parser.parse_args()
    if Path(args.store).resolve() == Path(args.output).resolve():
        parser.error("output must differ from the database path")
    policy = load_policy(ROOT / "examples/recommendation/policy.yml")
    store = RunStore(args.store)
    parent = None
    for version, auc in [("synthetic-baseline", 0.86), ("synthetic-regression", 0.70),
                         ("synthetic-candidate", 0.88)]:
        evidence = json.loads((ROOT / "examples/recommendation/evidence.json").read_text())
        # Original provenance is explicitly a synthetic fixture. No live experiment is claimed.
        evidence["provenance"]["model"]["name"] = "synthetic-recommendation-demo"
        evidence["provenance"]["model"]["version"] = version
        evidence["provenance"]["collector"]["name"] = "synthetic-workspace-demo"
        evidence["provenance"]["run"] = {
            "system": "synthetic-fixture", "id": version,
            "uri": (ROOT / "examples/recommendation/evidence.json").as_uri(),
        }
        evidence["metrics"]["candidate"]["auc"] = auc
        evidence["metrics"]["candidate"]["catalog_coverage"] = 0.70
        run = store.record(policy, evidence, actor="synthetic-demo", parent_id=parent)
        parent = run["id"]
    Path(args.output).write_text(render_workspace(store.list()), encoding="utf-8")
    print(f"Synthetic workspace: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
