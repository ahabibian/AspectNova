import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[ERROR] File not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"[ERROR] Invalid JSON in {path}: {e}")


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _coerce_eii_score(eii_result: Dict[str, Any]) -> Tuple[int, str]:
    raw = eii_result.get("eii_score")
    if isinstance(raw, dict):
        return int(raw.get("value", 0)), str(raw.get("grade", ""))
    if isinstance(raw, (int, float)):
        return int(raw), ""
    return 0, ""


def _energy_block(eii: Dict[str, Any], period: str) -> Dict[str, Any]:
    impact = eii.get("energy_impact", {})
    block = impact.get(period, {})
    return {
        "energy_kwh": float(block.get("energy_kwh", block.get("kwh", 0)) or 0),
        "co2_kg": float(block.get("co2_kg", 0) or 0),
        "cost_sek": float(block.get("cost_sek", 0) or 0),
    }


def build_payload(
    scan_result: Dict[str, Any],
    scan_canonical: Dict[str, Any],
    eii_result: Dict[str, Any],
) -> Dict[str, Any]:

    stats = scan_result.get("stats", {})
    total_files = int(stats.get("total_files", 0))
    total_bytes = int(stats.get("total_bytes", 0))

    monthly = _energy_block(eii_result, "monthly")
    annual = _energy_block(eii_result, "annual")
    eii_value, eii_grade = _coerce_eii_score(eii_result)

    return {
        "schema_id": "scan-payload",
        "schema_version": "v1",
        "generated_at": _now_iso(),
        "data_source": "local_pipeline",
        "scan": {
            "canonical": scan_canonical,
            "raw": scan_result,
        },
        "eii": {
            "energy_impact": {
                "monthly": monthly,
                "annual": annual,
            },
            "eii_score": {
                "value": eii_value,
                "grade": eii_grade,
            },
        },
        "kpis": {
            "files_scanned": total_files,
            "total_size_bytes": total_bytes,
            "energy_kwh_month": monthly["energy_kwh"],
            "energy_kwh_year": annual["energy_kwh"],
            "co2_kg_month": monthly["co2_kg"],
            "co2_kg_year": annual["co2_kg"],
            "cost_sek_month": monthly["cost_sek"],
            "cost_sek_year": annual["cost_sek"],
            "eii_score_value": eii_value,
            "eii_grade": eii_grade,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True)
    ap.add_argument("--scan-canonical", required=True)
    ap.add_argument("--eii", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = build_payload(
        _read_json(Path(args.scan)),
        _read_json(Path(args.scan_canonical)),
        _read_json(Path(args.eii)),
    )

    _write_json(Path(args.out), payload)
    print(f"OK -> wrote: {args.out}")


if __name__ == "__main__":
    main()
