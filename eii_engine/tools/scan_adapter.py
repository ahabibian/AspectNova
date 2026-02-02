from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCAN_SCHEMA_ID = "aspectnova.scan_result"
SCAN_SCHEMA_VERSION = "aspectnova.scan_result.v1"

GEN_NAME = "scan_adapter"
GEN_VERSION = "1.0.0"


# -------------------------
# helpers
# -------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_first(d: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return default
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return default
            # allow "123.0"
            return int(float(s))
        return default
    except Exception:
        return default


def to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return default
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return default
            return float(s)
        return default
    except Exception:
        return default


def ensure_min_len(s: str, n: int, prefix: str = "id-") -> str:
    s = (s or "").strip()
    if len(s) >= n:
        return s
    # deterministic-ish fallback
    return f"{prefix}{s}" if s else f"{prefix}{'x'* (n-len(prefix))}"


# -------------------------
# extraction
# -------------------------

def extract_assets(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Produce: assets: [{ref, size_bytes, is_candidate? ...}] BUT only keys allowed by schema.
    Since we don't have schema here, we keep it minimal: ref + size_bytes + optional tags if you later add.
    """
    # typical locations (you may adjust):
    # raw["scan"]["assets"] or raw["assets"] or raw["files"] ...
    scan = raw.get("scan") or {}
    candidates = []

    assets = []
    for key in ("assets", "files", "items"):
        v = scan.get(key)
        if isinstance(v, list):
            assets = v
            break
    if not assets and isinstance(raw.get("assets"), list):
        assets = raw["assets"]

    out: List[Dict[str, Any]] = []
    for i, a in enumerate(assets):
        if not isinstance(a, dict):
            continue

        ref = pick_first(a, ["ref", "id", "path", "uri", "name"])
        # Make ref non-empty
        ref_str = str(ref) if ref is not None else f"asset-{i:03d}"

        size = pick_first(a, ["size_bytes", "size", "bytes", "file_size_bytes"])
        size_bytes = to_int(size, 0)

        out.append({
            "ref": ref_str,
            "size_bytes": size_bytes,
        })

    return out


def extract_kpis(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Must output:
      storage_bytes_total
      storage_bytes_candidate
      energy_kwh_per_month
      co2_g_per_month
    We accept input variants:
      storage_tb_total / storage_bytes_total / storage_total_bytes ...
      energy_kwh_month / energy_kwh_per_month ...
      co2_g_month / co2_g_per_month ...
    """
    scan = raw.get("scan") or {}
    k = scan.get("kpis") if isinstance(scan.get("kpis"), dict) else {}
    if not k and isinstance(raw.get("kpis"), dict):
        k = raw["kpis"]

    storage_total = pick_first(k, [
        "storage_bytes_total", "storage_total_bytes",
        "storage_tb_total", "storage_total_tb",
    ])
    storage_cand = pick_first(k, [
        "storage_bytes_candidate", "storage_candidate_bytes",
        "storage_tb_candidate", "storage_candidate_tb",
    ])
    energy = pick_first(k, ["energy_kwh_per_month", "energy_kwh_month"])
    co2 = pick_first(k, ["co2_g_per_month", "co2_g_month"])

    # If TB given, convert to bytes (decimal TB assumed here; change if you use TiB)
    def tb_to_bytes(x: Any) -> int:
        tb = to_float(x, 0.0)
        return int(tb * 1_000_000_000_000)

    storage_bytes_total = (
        to_int(storage_total, 0)
        if "bytes" in str(type(storage_total)).lower() or isinstance(storage_total, (int, float))
        else tb_to_bytes(storage_total)
    )
    storage_bytes_candidate = (
        to_int(storage_cand, 0)
        if "bytes" in str(type(storage_cand)).lower() or isinstance(storage_cand, (int, float))
        else tb_to_bytes(storage_cand)
    )

    # If total/candidate not provided, we can derive from assets list as last resort
    if storage_bytes_total <= 0 or storage_bytes_candidate < 0:
        assets = extract_assets(raw)
        total_from_assets = sum(to_int(a.get("size_bytes"), 0) for a in assets)
        if storage_bytes_total <= 0:
            storage_bytes_total = total_from_assets
        # candidate: if you later mark candidates, derive; for now default 0 if missing
        if storage_bytes_candidate < 0:
            storage_bytes_candidate = 0

    return {
        "storage_bytes_total": int(storage_bytes_total),
        "storage_bytes_candidate": int(storage_bytes_candidate),
        "energy_kwh_per_month": float(to_float(energy, 0.0)),
        "co2_g_per_month": float(to_float(co2, 0.0)),
    }


def extract_source(raw: Dict[str, Any], input_name: str) -> Dict[str, Any]:
    scan = raw.get("scan") or {}
    src = raw.get("source") if isinstance(raw.get("source"), dict) else {}

    scan_id = pick_first(scan, ["scan_id", "id"])
    if scan_id is None:
        scan_id = pick_first(src, ["scan_id", "id"])
    scan_id = ensure_min_len(str(scan_id) if scan_id is not None else "scan-local", 8, prefix="scan-")

    payload_name = pick_first(src, ["payload_name", "source_payload_name"]) or input_name
    payload_schema_version = pick_first(src, ["payload_schema_version"]) or "unknown"

    return {
        "scan_id": scan_id,
        "payload_name": str(payload_name),
        "payload_schema_version": str(payload_schema_version),
    }


# -------------------------
# main adapter
# -------------------------

def adapt_scan(raw: Dict[str, Any], input_name: str) -> Dict[str, Any]:
    assets = extract_assets(raw)
    kpis = extract_kpis(raw)
    source = extract_source(raw, input_name)

    # Build canonical (NO extra fields)
    return {
        "schema_id": SCAN_SCHEMA_ID,
        "schema_version": SCAN_SCHEMA_VERSION,
        "meta": {
            "generated_at": utc_now_iso(),
            "generator": {
                "name": GEN_NAME,
                "version": GEN_VERSION,
            },
        },
        "source": source,
        "assets": assets,
        "kpis": kpis,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("in_scan", type=str)
    ap.add_argument("out_scan", type=str)
    args = ap.parse_args()

    in_path = Path(args.in_scan)
    out_path = Path(args.out_scan)

    raw = load_json(in_path)
    canonical = adapt_scan(raw, input_name=in_path.name)
    write_json(out_path, canonical)
    print(f"[scan_adapter] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
