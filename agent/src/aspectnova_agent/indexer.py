from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


INDEX_SCHEMA_VERSION = "scan_index_v1"


def build_index(cfg: Dict[str, Any]) -> Path:
    out_dir = Path(cfg["output"]["dir"]).resolve()
    canonical_path = out_dir / "scan_result.canonical.json"
    index_path = out_dir / "scan_index.v1.json"

    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    files = payload.get("files", []) or []
    stats = payload.get("stats", {}) or {}

    # Build a minimal, stable index
    by_ext = dict(stats.get("by_ext", {}) or {})
    largest = sorted(
        (
            {"path": f.get("path"), "size_bytes": f.get("size_bytes", 0)}
            for f in files
            if isinstance(f, dict)
        ),
        key=lambda x: int(x.get("size_bytes") or 0),
        reverse=True,
    )[:25]

    index_doc = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": payload.get("generated_at"),
        "root": payload.get("root"),
        "summary": {
            "file_count": stats.get("file_count", len(files)),
            "total_size_bytes": stats.get("total_size_bytes", 0),
            "hidden_count": stats.get("hidden_count", 0),
        },
        "by_ext": by_ext,
        "largest_files": largest,
    }

    index_path.write_text(json.dumps(index_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path
