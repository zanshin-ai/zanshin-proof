"""Load and enforce Zanshin Proof's versioned JSON Schema contracts."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


class DocumentValidationError(ValueError):
    """Raised when a document violates its public schema contract."""


def load_schema(name: str) -> dict[str, Any]:
    resource = files("zanshin_proof.schemas").joinpath(f"{name}.schema.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def validate_document(document: Any, schema_name: str) -> None:
    schemas = {name: load_schema(name) for name in ("policy", "evidence", "report", "decisions")}
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    validator = Draft202012Validator(
        schemas[schema_name],
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if not errors:
        return

    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path) or "$"
    raise DocumentValidationError(f"{schema_name} schema violation at {location}: {error.message}")
