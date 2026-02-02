from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from eii_engine import compute_eii


# -------------------------
# IO
# -------------------------

def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# -------------------------
# Scan
# -------------------------

def resolve_root(payload: Dict[str, Any]) -> Path:
    scan = payload.get("scan", {}) or {}
    root_raw = scan.get("root")
    if not root_raw:
        raise ValueError("payload.scan.root is missing")

    root_expanded = os.path.expandvars(root_raw)
    root = Path(root_expanded).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        raise ValueError(f"scan.root does not exist or is not a directory: {root}")

    return root


def walk_files(root: Path, max_files: int, max_depth: int) -> List[Path]:
    files: List[Path] = []
    root_str = str(root)

    for dirpath, dirnames, filenames in os.walk(root_str):
        # depth control
        rel = os.path.relpath(dirpath, root_str)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []  # stop descending
            continue

        for name in filenames:
            if len(files) >= max_files:
                return files
            p = Path(dirpath) / name
            files.append(p)

    return files


def normalize_assumptions(payload: Dict[str, Any]) -> Dict[str, Any]:
    a = payload.get("assumptions", {}) or {}
    return {
        "region": a.get("region", "SE"),
        "energy_per_tb_month_kwh": a.get("energy_per_tb_month_kwh", 3.0),
        "co2_g_per_kwh": a.get("co2_g_per_kwh", 50.0),
        "electricity_price_sek_per_kwh": a.get("electricity_price_sek_per_kwh", 1.5),
        "reclaimable_fraction_default": a.get("reclaimable_fraction_default", 0.25),
        "data_source": "filesystem",
    }


def build_cfg(assumptions: Dict[str, Any]) -> Dict[str, Any]:
    # Provide BOTH flat + nested, so any compute_eii implementation works
    cfg = {"assumptions": dict(assumptions)}
    cfg.update({
        "region": assumptions["region"],
        "energy_per_tb_month_kwh": assumptions["energy_per_tb_month_kwh"],
        "co2_g_per_kwh": assumptions["co2_g_per_kwh"],
        "electricity_price_sek_per_kwh": assumptions["electricity_price_sek_per_kwh"],
        "reclaimable_fraction_default": assumptions["reclaimable_fraction_default"],
        "data_source": assumptions.get("data_source", "filesystem"),
    })
    return cfg


def reconcile_output(eii_result: Dict[str, Any], scan_root: Path, scan_agg: Dict[str, Any], assumptions: Dict[str, Any]) -> Dict[str, Any]:
    """
    If compute_eii returns empty aggregates/root, force output to reflect real scan.
    This keeps pipeline truthful and unblocks downstream proposals.
    """
    out = dict(eii_result)

    out.setdefault("source_scan", {})
    out.setdefault("aggregates", {})
    out.setdefault("assumptions", {})

    out["assumptions"].update(assumptions)

    # If root missing or empty -> set it
    if not out["source_scan"].get("root"):
        out["source_scan"]["root"] = str(scan_root)

    # If aggregates are zero but scan says otherwise -> overwrite aggregates
    out_fc = float(out["aggregates"].get("file_count", 0) or 0)
    scan_fc = float(scan_agg.get("file_count", 0) or 0)

    if out_fc == 0 and scan_fc > 0:
        out["aggregates"] = dict(scan_agg)

        # Minimal energy impact (monthly/annual) from scanned TB
        total_gb = float(scan_agg.get("total_size_gb", 0.0) or 0.0)
        total_tb = total_gb / 1024.0

        energy_kwh_month = total_tb * float(assumptions["energy_per_tb_month_kwh"])
        co2_kg_month = (energy_kwh_month * float(assumptions["co2_g_per_kwh"])) / 1000.0
        cost_sek_month = energy_kwh_month * float(assumptions["electricity_price_sek_per_kwh"])

        out["energy_impact"] = {
            "monthly": {
                "energy_kwh": round(energy_kwh_month, 6),
                "co2_kg": round(co2_kg_month, 6),
                "cost_sek": round(cost_sek_month, 6),
            },
            "annual": {
                "energy_kwh": round(energy_kwh_month * 12.0, 6),
                "co2_kg": round(co2_kg_month * 12.0, 6),
                "cost_sek": round(cost_sek_month * 12.0, 6),
            },
        }

        # Minimal optimization potential (reclaimable fraction default)
        reclaimable_gb = total_gb * float(assumptions["reclaimable_fraction_default"])
        out["optimization_potential"] = {
            "reclaimable_storage_gb": round(reclaimable_gb, 6),
            "energy_saving_kwh_year": round((reclaimable_gb / 1024.0) * float(assumptions["energy_per_tb_month_kwh"]) * 12.0, 6),
            "co2_reduction_kg_year": round((((reclaimable_gb / 1024.0) * float(assumptions["energy_per_tb_month_kwh"]) * 12.0) * float(assumptions["co2_g_per_kwh"])) / 1000.0, 6),
            "cost_saving_sek_year": round(((reclaimable_gb / 1024.0) * float(assumptions["energy_per_tb_month_kwh"]) * 12.0) * float(assumptions["electricity_price_sek_per_kwh"]), 6),
        }

    return out


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_eii.py", description="Filesystem scan -> compute EII")
    parser.add_argument("--scan", required=True, help="Path to scan payload JSON")
    parser.add_argument("--out", required=True, help="Output path for eii_result.json")
    args = parser.parse_args()

    out_path = Path(args.out).resolve()
    try:
        if out_path.exists():
            out_path.unlink()
    except Exception:
        pass

    try:
        payload = read_json(Path(args.scan).resolve())
    except Exception as e:
        print(f"[run_eii] Payload error: {e}")
        return 2

    try:
        root = resolve_root(payload)
    except Exception as e:
        print(f"[run_eii] Scan root error: {e}")
        return 3

    scan_cfg = payload.get("scan", {}) or {}
    limits = scan_cfg.get("limits", {}) or {}
    max_files = int(limits.get("max_files", 5000))
    max_depth = int(limits.get("max_depth", 12))

    print(f"[run_eii] Scanning root: {root}")

    files = walk_files(root, max_files=max_files, max_depth=max_depth)
    if not files:
        print("[run_eii] ERROR: scan completed but found 0 files")
        return 4

    total_bytes = 0
    by_ext: Dict[str, int] = {}
    for f in files:
        try:
            size = f.stat().st_size
        except OSError:
            continue
        total_bytes += size
        ext = f.suffix.lower() or "no_ext"
        by_ext[ext] = by_ext.get(ext, 0) + size

    total_gb = total_bytes / (1024 ** 3)
    scan_agg = {
        "file_count": len(files),
        "total_size_bytes": total_bytes,
        "total_size_gb": round(total_gb, 6),
        "by_extension_gb": {k: round(v / (1024 ** 3), 6) for k, v in by_ext.items()},
    }

    assumptions = normalize_assumptions(payload)
    cfg = build_cfg(assumptions)

    scan_result = {
        "schema_id": "scan-result",
        "schema_version": "aspectnova.scan_result.v1",
        "context": payload.get("context", {}) or {},
        "source_scan": {"root": str(root), "file_count": len(files)},
        "aggregates": dict(scan_agg),
        "assumptions": dict(assumptions),
        "region": assumptions["region"],
    }

    # Debug artifact: so we can prove scan_result is correct
    try:
        write_json(Path("out/scan_result.debug.json"), scan_result)
    except Exception:
        pass

    try:
        eii_result = compute_eii(scan_result, cfg)
    except Exception as e:
        print(f"[run_eii] compute_eii failed: {e}")
        return 6

    # Reconcile: ensure output matches real scan
    eii_result_fixed = reconcile_output(eii_result, root, scan_agg, assumptions)
    write_json(out_path, eii_result_fixed)

    print(f"[run_eii] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
