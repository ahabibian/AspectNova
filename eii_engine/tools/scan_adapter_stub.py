from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

# -------------------------
# Utils
# -------------------------

def die(msg: str):
    print(f"[scan_adapter_stub] {msg}", file=sys.stderr)
    sys.exit(2)

def load_json(p: str) -> Dict[str, Any]:
    path = Path(p)
    if not path.exists():
        die(f"Input not found: {p}")
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(p: str, obj: Dict[str, Any]):
    path = Path(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def to_int(v):
    try:
        return int(float(v))
    except Exception:
        return None

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# -------------------------
# Asset normalization
# -------------------------

def normalize_assets(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_assets = raw.get("assets") or raw.get("files")
    if not isinstance(raw_assets, list):
        die("Raw scan has no assets/files list")

    assets = []
    for i, a in enumerate(raw_assets):
        if not isinstance(a, dict):
            die(f"Asset[{i}] invalid")

        ref = a.get("path") or a.get("name") or a.get("id")
        size = a.get("size_bytes") or a.get("size") or a.get("bytes")

        size_i = to_int(size)
        if not ref or size_i is None:
            die(f"Asset[{i}] missing ref or size")

        assets.append({
            "ref": str(ref),
            "size_bytes": size_i
        })

    return assets

# -------------------------
# KPI calculation
# -------------------------

def calculate_kpis(assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_bytes = sum(a["size_bytes"] for a in assets)
    candidate_bytes = total_bytes  # placeholder rule

    ENERGY_KWH_PER_TB_MONTH = 2.0
    CO2_G_PER_KWH = 400.0

    tb = total_bytes / 1_000_000_000_000
    energy = tb * ENERGY_KWH_PER_TB_MONTH
    co2 = energy * CO2_G_PER_KWH

    return {
        "storage_bytes_total": total_bytes,
        "storage_bytes_candidate": candidate_bytes,
        "energy_kwh_per_month": round(energy, 4),
        "co2_g_per_month": round(co2, 2)
    }

# -------------------------
# Build canonical scan_result
# -------------------------

def build_canonical(raw: Dict[str, Any]) -> Dict[str, Any]:
    scan = raw.get("scan") if isinstance(raw.get("scan"), dict) else raw

    assets = normalize_assets(scan)
    kpis = calculate_kpis(assets)

    scan_id = scan.get("scan_id") or f"scan-{uuid.uuid4()}"

    return {
        "schema_id": "aspectnova.scan_result",
        "schema_version": "aspectnova.scan_result.v1",
        "meta": {
            "generated_at": now_iso(),
            "generator": {
                "name": "scan_adapter_stub",
                "version": "0.1.0"
            }
        },
        "source": {
            "scan_id": scan_id,
            "payload_name": "scan_result.json",
            "payload_schema_version": "aspectnova.scan_payload.v1"
        },
        "assets": assets,
        "kpis": kpis
    }

# -------------------------
# CLI
# -------------------------

def main():
    if len(sys.argv) != 3:
        die("Usage: scan_adapter_stub.py <in_scan.json> <out_canonical.json>")

    raw = load_json(sys.argv[1])
    canonical = build_canonical(raw)
    write_json(sys.argv[2], canonical)

    print(f"[scan_adapter_stub] OK -> wrote: {sys.argv[2]}")

if __name__ == "__main__":
    main()
