import json
import re

from zanshin_proof.dashboard import render_workspace


def test_embedded_payload_cannot_close_script_or_inject_markup():
    label = '</script><img src=x onerror="alert(1)"> & \u2028'
    rendered = render_workspace([{"actor": label}])
    assert label not in rendered
    match = re.search(r'<script id="proof-data" type="application/json">(.*?)</script>', rendered)
    assert json.loads(match.group(1))["runs"][0]["actor"] == label
    assert "__PROOF_DATA__" not in rendered


def test_empty_workspace_has_no_external_asset_dependencies():
    rendered = render_workspace([])
    assert 'src="http' not in rendered
    assert 'href="http' not in rendered
    assert "No projects yet" in rendered
