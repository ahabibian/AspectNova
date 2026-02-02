from __future__ import annotations

import json
from pathlib import Path

from agent.config import load_config
from agent.scanner import scan_and_write_outputs


def test_output_schema_v1(tmp_path: Path):
    # config
    cfg = load_config("config.v1.yaml")

    # make a tiny directory
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("hello", encoding="utf-8")
    (root / "b.log").write_text("world", encoding="utf-8")

    # run scan -> writes output/scan_result*.json
    raw_path, canon_path = scan_and_write_outputs(cfg, override_root=str(root))

    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    canon = json.loads(Path(canon_path).read_text(encoding="utf-8"))

    assert raw["schema_id"] == "scan-result"
    assert raw["schema_version"] == "v1"
    assert canon["schema_id"] == "scan-result"
    assert canon["schema_version"] == "v1"

    assert isinstance(raw["files"], list)
    assert isinstance(canon["files"], list)
    assert raw["stats"]["total_files"] == 2
    assert canon["stats"]["total_files"] == 2
