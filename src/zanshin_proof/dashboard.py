"""Export a portable review workspace. No server, scripts from a CDN, or network calls."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any


def render_workspace(runs: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        {"exported_at": datetime.now(UTC).isoformat(), "runs": runs},
        allow_nan=False, ensure_ascii=True,
    ).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = files("zanshin_proof").joinpath("workspace.html").read_text(encoding="utf-8")
    return template.replace("__PROOF_DATA__", payload)
