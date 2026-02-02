from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def decide_priority(eii_grade: str, eii_score: int, total_size_bytes: int) -> Dict[str, Any]:
    """
    Deterministic v1 decision rules (simple, explainable, stable).
    Later we can version rules without breaking contract.
    """
    g = (eii_grade or "").strip().upper()

    # Priority baseline by grade
    if g in ("A",):
        priority = "low"
        confidence = 0.85
    elif g in ("B",):
        priority = "medium"
        confidence = 0.8
    elif g in ("C", "D"):
        priority = "high"
        confidence = 0.8
    else:
        # fallback using score
        if eii_score >= 80:
            priority = "low"
        elif eii_score >= 60:
            priority = "medium"
        else:
            priority = "high"
        confidence = 0.6

    # Small datasets: reduce urgency (but keep classification)
    if total_size_bytes < 10_000_000:  # < ~10MB
        confidence = min(confidence, 0.7)

    risk_bucket = g if g else ("SCORE_" + ("HI" if eii_score < 60 else "MID" if eii_score < 80 else "LO"))

    explanations = [
        f"EII grade={g or 'N/A'} score={eii_score} used to set priority={priority}.",
        "Annual energy impact is derived from monthly KPI (monthly*12, rounded).",
    ]

    return {
        "priority": priority,
        "risk_bucket": risk_bucket,
        "confidence": float(confidence),
        "explanations": explanations,
    }


def build_policy_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    kpis = payload.get("kpis", {}) or {}

    files_scanned = int(kpis.get("files_scanned", 0) or 0)
    total_size_bytes = int(kpis.get("total_size_bytes", 0) or 0)
    energy_kwh_month = float(kpis.get("energy_kwh_month", 0.0) or 0.0)
    energy_kwh_year = float(kpis.get("energy_kwh_year", 0.0) or 0.0)
    eii_score_value = int(kpis.get("eii_score_value", 0) or 0)
    eii_grade = str(kpis.get("eii_grade", "") or "")

    decision = decide_priority(eii_grade, eii_score_value, total_size_bytes)

    # Actions: v1 placeholder (since canonical currently doesn't have file-level signals)
    actions = [
        {
            "action_id": "dedupe_candidates",
            "title": "Find duplicates",
            "severity": "medium" if decision["priority"] in ("medium", "high") else "low",
            "estimated_savings_bytes": 0,
            "notes": "Placeholder: requires file-level signals in scan.canonical later.",
        }
    ]

    return {
        "schema_id": "policy-decision",
        "schema_version": "v1",
        "generated_at": _iso_now(),
        "policy": {
            "policy_id": "storage.cleanup.v1",
            "policy_version": "1.0.0",
        },
        "inputs": {
            "files_scanned": files_scanned,
            "total_size_bytes": total_size_bytes,
            "energy_kwh_month": energy_kwh_month,
            "energy_kwh_year": energy_kwh_year,
            "eii_score_value": eii_score_value,
            "eii_grade": eii_grade.strip().upper(),
        },
        "decision": decision,
        "actions": actions,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Path to scan_payload.json")
    ap.add_argument("--out", dest="out", required=True, help="Path to policy_decision.json")
    args = ap.parse_args()

    payload = _read_json(Path(args.inp))
    out_obj = build_policy_decision(payload)
    _write_json(Path(args.out), out_obj)

    print(f"OK -> wrote: {args.out}")


if __name__ == "__main__":
    main()
