from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import yaml

from aspectnova_agent.scanner import scan_directory, build_raw_payload


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml_safe(p: Path) -> tuple[dict, str | None]:
    if not p.exists():
        return {}, None
    try:
        txt = p.read_text(encoding="utf-8-sig")
    except Exception as e:
        return {}, f"config_read_error: {e}"
    try:
        data = yaml.safe_load(txt)
        return (data or {}), None
    except Exception as e:
        return {}, f"config_yaml_error: {e}"


def _resolve_run_id(argv: list[str]) -> str | None:
    # Support BOTH:
    # 1) python run_scan_stage.py <run_id>          (pipeline contract)
    # 2) python run_scan_stage.py --run-id <run_id> (dev/cli)
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--run-id")
    args, rest = ap.parse_known_args(argv[1:])
    if args.run_id:
        return args.run_id
    if len(rest) >= 1 and not rest[0].startswith("-"):
        return rest[0]
    if len(argv) >= 2 and not argv[1].startswith("-"):
        return argv[1]
    return None


def main(argv: list[str]) -> int:
    # parse only non-critical args after run_id resolution
    run_id = _resolve_run_id(argv)
    if not run_id:
        print("usage: python .\\run_scan_stage.py <run_id> OR --run-id <run_id> [--config ...] [--root ...]")
        return 2

    ap = argparse.ArgumentParser()
    ap.add_argument("run_id_pos", nargs="?", help="run_id (positional) for pipeline")
    ap.add_argument("--run-id", dest="run_id_opt")
    ap.add_argument("--config", default="config.v1.yaml")
    ap.add_argument("--root", default=None, help="Override scan root directory")
    args = ap.parse_args(argv[1:])

    cfg_path = Path(args.config)
    cfg, cfg_err = _read_yaml_safe(cfg_path)

    cfg_scan = (cfg.get("scan") or {}) if isinstance(cfg, dict) else {}
    cfg_root = None
    if isinstance(cfg_scan, dict):
        cfg_root = cfg_scan.get("root") or cfg_scan.get("scan_root")
    if cfg_root is None and isinstance(cfg, dict):
        cfg_root = cfg.get("root") or cfg.get("workspace_root")

    scan_root = args.root or cfg_root or str(Path(".").resolve())

    exclude_dirs = ["node_modules", ".git", ".venv", "__pycache__"]
    include_exts: list[str] = []
    hash_max_bytes = 0
    if isinstance(cfg_scan, dict):
        exclude_dirs = list(cfg_scan.get("exclude_dirs", exclude_dirs))
        include_exts = list(cfg_scan.get("include_extensions", include_exts))
        hash_max_bytes = int(cfg_scan.get("hash_max_bytes", hash_max_bytes))

    root = Path("runs") / run_id
    in_dir = root / "input"
    out_dir = root / "output"
    evidence_dir = out_dir / "evidence"
    in_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    scan_obj = scan_directory(
        scan_root,
        exclude_dirs=exclude_dirs,
        include_extensions=include_exts,
        hash_max_bytes=hash_max_bytes,
    )
    raw = build_raw_payload(scan_obj)

    # --- ABS_PATH_NORMALIZATION (critical for owner_enricher)
    try:
        base = Path(scan_root).resolve()
        items = raw.get("items") or raw.get("files") or []

        for it in items:
            p = str(it.get("path") or "")
            if not p:
                continue

            P = Path(p)

            if not P.is_absolute():
                P = (base / P).resolve()
            else:
                P = P.resolve()

            it["path"] = str(P)

    except Exception:
        pass



    out_path = in_dir / "scan_result.json"
    out_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (evidence_dir / "_tmp_scan_stage.log").write_text(
        json.dumps(
            {
                "status": "OK",
                "stage": "scan_stage",
                "run_id": run_id,
                "generated_at_utc": _utc_now_iso(),
                "config_path": str(cfg_path),
                "config_error": cfg_err,
                "scan_root": scan_root,
                "exclude_dirs": exclude_dirs,
                "include_extensions": include_exts,
                "hash_max_bytes": hash_max_bytes,
                "written": str(out_path),
                "stats": raw.get("stats"),
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print("SCAN_STAGE DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
