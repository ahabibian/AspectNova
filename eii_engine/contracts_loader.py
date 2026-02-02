from __future__ import annotations

from typing import Any, Dict
from jsonschema import Draft202012Validator


class ValidationError(Exception):
    pass


def validate_json(instance: Any, schema: Dict[str, Any], *, label: str) -> None:
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(instance), key=lambda e: list(e.path))

    if errors:
        lines = [f"{label} validation failed ({len(errors)} errors):"]
        for e in errors[:25]:
            path = ".".join([str(p) for p in e.path]) or "<root>"
            lines.append(f"- {path}: {e.message}")
        raise ValidationError("\n".join(lines))
