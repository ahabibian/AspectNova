# run_scan.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

# Import from package (works when run from agent/src)
from agent.config import load_config  # type: ignore
import agent.cli as agent_cli  # type: ignore


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(prog="run-scan", description="Run AspectNova agent scan with guaranteed outputs.")
    ap.add_argument("--config", required=True, help="Path to config YAML (e.g. agent/config.v1.yaml)")
    ap.add_argument("--root", required=True, help="Absolute root path to scan (e.g. C:\\Users\\...\\OneDrive - Ericsson)")
    ap.add_argument("--out-dir", default=None, help="Absolute output dir. If omitted, creates agent/runs/scan_manual_<ts>/output")
    ap.add_argument("--run-name", default=None, help="Optional run folder name (default: scan_manual_<ts>)")

    args = ap.parse_args()

    cfg_path = Path(args.config).expanduser().resolve()
    root = Path(args.root).expanduser().resolve()

    if not cfg_path.exists():
        print(f"[error] config not found: {cfg_path}")
        return 2
    if not root.exists():
        print(f"[error] root not found: {root}")
        return 2

    cfg = load_config(str(cfg_path))

    # Decide output directory (absolute, predictable)
    ts = _utc_stamp()
    run_name = args.run_name or f"scan_manual_{ts}"

    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser().resolve()
    else:
        # Put outputs under AspectNova/agent/runs/<run_name>/output
        # This file lives in .../AspectNova/agent/src/run_scan.py
        # so repo root is .../AspectNova
        aspectnova_root = Path(__file__).resolve().parents[2]  # .../AspectNova
        out_dir = aspectnova_root / "agent" / "runs" / run_name / "output"

    out_dir.mkdir(parents=True, exist_ok=True)

    # Override config roots + output dir
    cfg.setdefault("scan", {})
    cfg["scan"]["roots"] = [str(root)]

    cfg.setdefault("output", {})
    cfg["output"]["dir"] = str(out_dir)

    print(f"[run] config : {cfg_path}")
    print(f"[run] root   : {root}")
    print(f"[run] outdir : {out_dir}")

    # Call the same writer used by cli.py (but now we guarantee cfg + outdir)
    agent_cli.scan_and_write_outputs(cfg, override_root=None)

    # Validate expected outputs exist
    expected = [
        out_dir / "scan_result.json",
        out_dir / "scan_result.canonical.json",
    ]
    missing = [p for p in expected if not p.exists()]

    # Some builds also create items via adapter; if present, show it
    items_path = out_dir / "scan_result.items.json"

    if missing:
        print("[error] scan finished but expected outputs are missing:")
        for p in missing:
            print(f" - {p}")
        return 3

    print("[ok] wrote:")
    for p in expected:
        print(f" - {p} ({p.stat().st_size} bytes)")
    if items_path.exists():
        print(f" - {items_path} ({items_path.stat().st_size} bytes)")
    else:
        print("[warn] scan_result.items.json not found in outdir (may require adapter step).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
