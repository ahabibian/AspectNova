from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator


class OutputSchemaError(Exception):
    pass


def load_output_schema(filename: str) -> Dict[str, Any]:
    """
    Load schema JSON from:
      - src/agent/schema/<filename>   (recommended)
      - or current working directory fallback
    """
    here = Path(__file__).resolve().parent
    p1 = here / "schema" / filename
    p2 = Path(filename)

    path = p1 if p1.exists() else p2
    if not path.exists():
        raise OutputSchemaError(f"Schema file not found: {filename} (looked at {p1} and {p2})")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise OutputSchemaError(f"Failed to read schema json: {path}: {e}") from e


def validate_output(payload: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """
    Strict validation. Raises OutputSchemaError on failure.
    """
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        lines = ["Output does not match schema:"]
        for err in errors[:30]:
            loc = ".".join(str(p) for p in err.path) or "<root>"
            lines.append(f"- {loc}: {err.message}")
        raise OutputSchemaError("\n".join(lines))
