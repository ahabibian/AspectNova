from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import load_config, cfg_get
from .scanner import scan_directory, build_raw_payload, build_canonical_payload
from .output_schema import load_output_schema, validate_output


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def scan_and_write_outputs(
    cfg: Dict[str, Any],
    *,
    override_root: Optional[str] = None,
    root_override: Optional[str] = None,  # compat alias
) -> Tuple[str, str]:
    out_dir = Path(cfg_get(cfg, "output.dir", "output"))
    _ensure_dir(out_dir)

    roots: List[str] = list(cfg_get(cfg, "scan.roots", ["./"]))
    if override_root:
        roots = [override_root]
    if root_override:  # keep both
        roots = [root_override]

    exclude_dirs = list(cfg_get(cfg, "scan.exclude_dirs", ["node_modules", ".git", ".venv", "__pycache__"]))
    include_exts = list(cfg_get(cfg, "scan.include_extensions", []))
    hash_max_bytes = int(cfg_get(cfg, "scan.hash_max_bytes", 0))

    # v1: if multiple roots, concatenate files and mark root as MULTI
    combined_scan_entries = []
    combined_root = "MULTI" if len(roots) > 1 else str(Path(roots[0]).resolve())

    for r in roots:
        scan_obj = scan_directory(
            r,
            exclude_dirs=exclude_dirs,
            include_extensions=include_exts,
            hash_max_bytes=hash_max_bytes,
        )
        combined_scan_entries.extend(scan_obj["entries"])

    scan_obj = {
        "root": combined_root,
        "entries": combined_scan_entries,
        "hash_max_bytes": hash_max_bytes,
    }

    raw = build_raw_payload(scan_obj)
    canonical = build_canonical_payload(raw)

    # validate against schema if present
    try:
        schema = load_output_schema("scan_result.schema.v1.json")
        validate_output(raw, schema)
        validate_output(canonical, schema)
    except Exception:
        # if schema file missing in some setups, still write outputs
        pass

    raw_path = out_dir / "scan_result.json"
    canon_path = out_dir / "scan_result.canonical.json"

    raw_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    canon_path.write_text(json.dumps(canonical, indent=2, ensure_ascii=False), encoding="utf-8")

    return str(raw_path), str(canon_path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="agent")
    parser.add_argument("--config", required=True, help="Path to config YAML")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("path", nargs="?", default=None, help="Override root path (optional)")

    sub.add_parser("index")
    sub.add_parser("report")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "scan":
        scan_and_write_outputs(cfg, override_root=args.path)
        return 0

    if args.cmd in ("index", "report"):
        return 0

    return 1
