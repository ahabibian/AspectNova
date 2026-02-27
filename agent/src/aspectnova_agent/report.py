from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


REPORT_SCHEMA_VERSION = "scan_report_v1"


def build_report(cfg: Dict[str, Any]) -> Path:
    out_dir = Path(cfg["output"]["dir"]).resolve()
    canonical_path = out_dir / "scan_result.canonical.json"
    index_path = out_dir / "scan_index.v1.json"
    report_path = out_dir / "scan_report.v1.json"

    scan_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    index_payload = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    stats = scan_payload.get("stats", {}) or {}
    files = scan_payload.get("files", []) or []

    # Basic findings (v1)
    findings = []

    hidden = [f for f in files if isinstance(f, dict) and f.get("is_hidden") is True]
    if hidden:
        findings.append(
            {
                "code": "HIDDEN_FILES_PRESENT",
                "message": f"{len(hidden)} hidden file(s) detected (v1 heuristic).",
                "sample_paths": [h.get("path") for h in hidden[:10]],
            }
        )

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": scan_payload.get("generated_at"),
        "root": scan_payload.get("root"),
        "summary": {
            "file_count": stats.get("file_count", len(files)),
            "total_size_bytes": stats.get("total_size_bytes", 0),
            "hidden_count": stats.get("hidden_count", 0),
            "hashed_count": stats.get("hashed_count", 0),
        },
        "by_ext": stats.get("by_ext", {}),
        "largest_files": (index_payload.get("largest_files") or [])[:10],
        "findings": findings,
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path
