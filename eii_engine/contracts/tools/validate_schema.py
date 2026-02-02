from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[validate_schema] Failed to read JSON: {path} ({e})")


def load_schema(path: Path) -> Dict[str, Any]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[validate_schema] Failed to read schema JSON: {path} ({e})")
    if not isinstance(schema, dict):
        raise SystemExit(f"[validate_schema] Schema root must be an object: {path}")
    return schema


def validate(instance: Any, schema: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        v = Draft202012Validator(schema)
        errors = sorted(v.iter_errors(instance), key=lambda e: e.path)
        if errors:
            msg_lines = []
            for err in errors[:50]:  # cap noise
                path = "$"
                if err.path:
                    path += "." + ".".join(str(p) for p in err.path)
                msg_lines.append(f"- {path}: {err.message}")
            if len(errors) > 50:
                msg_lines.append(f"... and {len(errors) - 50} more")
            return False, "\n".join(msg_lines)
        return True, "OK"
    except ValidationError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Validator error: {e}"


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python tools/validate_schema.py <json_file> <schema_file>", file=sys.stderr)
        raise SystemExit(2)

    json_path = Path(sys.argv[1]).resolve()
    schema_path = Path(sys.argv[2]).resolve()

    if not json_path.exists():
        raise SystemExit(f"[validate_schema] JSON file not found: {json_path}")
    if not schema_path.exists():
        raise SystemExit(f"[validate_schema] Schema file not found: {schema_path}")

    instance = load_json(json_path)
    schema = load_schema(schema_path)

    ok, details = validate(instance, schema)
    if ok:
        print(f"[validate_schema] PASS: {json_path.name} vs {schema_path.name}")
        raise SystemExit(0)
    else:
        print(f"[validate_schema] FAIL: {json_path.name} vs {schema_path.name}", file=sys.stderr)
        print(details, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
