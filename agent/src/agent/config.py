from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

import yaml
from jsonschema import Draft202012Validator
from jsonschema.validators import extend


class ConfigError(Exception):
    pass


# -------------------------
# Config schema (strict) + defaults
# -------------------------
CONFIG_SCHEMA_V1: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "output", "scan"],
    "properties": {
        "schema_version": {
            "type": "string",
            "enum": ["config_v1"],
            "default": "config_v1",
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "required": ["dir"],
            "properties": {
                "dir": {"type": "string", "minLength": 1, "default": "output"},
            },
            "default": {"dir": "output"},
        },
        "scan": {
            "type": "object",
            "additionalProperties": False,
            "required": ["roots"],
            "properties": {
                # roots can be ["./"] or ["C:/path"] etc.
                "roots": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                    "default": ["./"],
                },
                "exclude_dirs": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "default": ["node_modules", ".git", ".venv", "__pycache__"],
                },
                # if empty => allow all extensions
                "include_extensions": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "default": [],
                },
                # 0 => do not hash
                "hash_max_bytes": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 0,
                },
            },
            "default": {
                "roots": ["./"],
                "exclude_dirs": ["node_modules", ".git", ".venv", "__pycache__"],
                "include_extensions": [],
                "hash_max_bytes": 0,
            },
        },
    },
}


def _extend_with_default(validator_class):
    """jsonschema defaults injection (Draft 2020-12)."""

    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        if isinstance(instance, dict):
            for prop, subschema in properties.items():
                if prop not in instance and "default" in subschema:
                    instance[prop] = subschema["default"]
        yield from validate_properties(validator, properties, instance, schema)

    return extend(validator_class, {"properties": set_defaults})


DefaultingDraft202012Validator = _extend_with_default(Draft202012Validator)


def load_config(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"Failed to read config file: {e}") from e

    if cfg is None:
        cfg = {}
    if not isinstance(cfg, dict):
        raise ConfigError("Config root must be a mapping (YAML object)")

    # Apply defaults + validate strictly
    validator = DefaultingDraft202012Validator(CONFIG_SCHEMA_V1)
    errors = sorted(validator.iter_errors(cfg), key=lambda e: list(e.path))

    if errors:
        lines = ["Config validation failed:"]
        for err in errors[:20]:
            loc = ".".join(str(p) for p in err.path) or "<root>"
            lines.append(f"- {loc}: {err.message}")
        raise ConfigError("\n".join(lines))

    return cfg


def cfg_get(cfg: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safe nested getter: cfg_get(cfg, "scan.roots") -> [...]
    """
    cur: Any = cfg
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
