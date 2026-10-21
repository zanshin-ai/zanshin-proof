from jsonschema import Draft202012Validator

from zanshin_proof.schema import load_schema, validate_document


def test_public_schemas_are_valid_draft_2020_12() -> None:
    for name in ("policy", "evidence", "report", "decisions"):
        Draft202012Validator.check_schema(load_schema(name))


def test_example_report_contract_accepts_provenance_reference() -> None:
    provenance = {
        "commit_sha": "521134ee3e9602a0e04843e2f5d1f60909df3173",
        "collected_at": "2026-08-26T23:45:00Z",
        "collector": {"name": "pytest", "version": "1"},
        "model": {"name": "recommendation", "version": "candidate"},
        "run": {"system": "mlflow", "id": "run-42"},
        "sources": [{"type": "table", "uri": "table://recommendation", "version": "42"}],
    }
    validate_document(
        {
            "project": "recommendation",
            "verdict": "pass",
            "policy_version": 1,
            "provenance": provenance,
            "summary": {"pass": 1, "warn": 0, "fail": 0, "error": 0},
            "checks": [
                {
                    "id": "ready",
                    "status": "pass",
                    "required": True,
                    "message": "ready",
                    "observed": True,
                    "expected": True,
                }
            ],
        },
        "report",
    )
