from __future__ import annotations

import json
from pathlib import Path

from agent.config import load_config
from agent.scanner import build_raw_payload
from agent.normalize import canonicalize_output  # backward compat alias (exists now)
from agent.output_schema import load_output_schema, validate_output


def test_output_schema_v1_matches():
    cfg = load_config("config.v1.yaml")
    root = Path(cfg["scan"]["roots"][0])

    raw = build_raw_payload(cfg, root=root)
    canonical = canonicalize_output(raw)

    schema = load_output_schema("scan_result.schema.v1.json")

    validate_output(raw, schema)
    validate_output(canonical, schema)
