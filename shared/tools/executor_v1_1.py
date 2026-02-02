from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


# -------------------------
# Errors
# -------------------------
class ExecutorError(Exception):
    pass


# -------------------------
# Models
# -------------------------
@dataclass(frozen=True)
class PolicyDecision:
    policy_id: str
    priority: str  # low|medium|high
    risk_bucket: str
    confidence: float
    reasons: List[str]


# -------------------------
# IO helpers
# -------------------------
def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ExecutorError(f"File not found: {path}") from None
    except json.JSONDecodeError as e:
        raise ExecutorError(f"Invalid JSON in {path}: {e}") from None


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# -------------------------
# Payload helpers
# -------------------------
def _extract_scan_stats(payload_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical KPI source:
      payload['eii']['kpis']  (as built by payload_builder.py)

    Fallbacks exist but we keep them minimal.
    """
    eii = payload_doc.get("eii") or {}
    kpis = eii.get("kpis") or {}

    # normalize keys we care about
    return {
        "files_scanned": kpis.get("files_scanned"),
        "total_size_bytes": kpis.get("total_size_bytes"),
        "energy_kwh_month": kpis.get("energy_kwh_month"),
        "energy_kwh_year": kpis.get("energy_kwh_year"),
        "co2_kg_month": kpis.get("co2_kg_month"),
        "co2_kg_year": kpis.get("co2_kg_year"),
        "cost_sek_month": kpis.get("cost_sek_month"),
        "cost_sek_year": kpis.get("cost_sek_year"),
        "eii_score_value": kpis.get("eii_score_value"),
        "eii_grade": kpis.get("eii_grade"),
    }


# -------------------------
# Policy parsing (tolerant)
# -------------------------
def _parse_policy_decision(policy_doc: Dict[str, Any]) -> PolicyDecision:
    """
    Supports BOTH shapes:

    A) legacy flat:
      { "policy_id": "...", "priority": "...", "risk_bucket": "...", "confidence": 0.7, "reasons": [...] }

    B) contract v1 (Policy Engine v1):
      {
        "policy": { "policy_id": "...", ... },
        "decision": { "priority": "...", "risk_bucket": "...", "confidence": 0.7, "reasons": [...] }
      }

    Also accepts policy_id under decision.policy_id if present.
    """
    root_policy_id = policy_doc.get("policy_id")

    decision_obj = policy_doc.get("decision") if isinstance(policy_doc.get("decision"), dict) else {}
    policy_obj = policy_doc.get("policy") if isinstance(policy_doc.get("policy"), dict) else {}

    policy_id = (
        root_policy_id
        or decision_obj.get("policy_id")
        or policy_obj.get("policy_id")
        or policy_obj.get("id")
    )

    if not policy_id:
        raise ExecutorError("policy_id is required (root.policy_id OR decision.policy_id OR policy.policy_id)")

    # priority & risk are expected in decision, but accept legacy flat too
    priority = (decision_obj.get("priority") or policy_doc.get("priority") or "").strip().lower()
    risk_bucket = (decision_obj.get("risk_bucket") or policy_doc.get("risk_bucket") or "").strip().upper()
    confidence = decision_obj.get("confidence", policy_doc.get("confidence", 0.0))

    reasons = decision_obj.get("reasons", policy_doc.get("reasons", []))
    if isinstance(reasons, str):
        reasons = [reasons]
    if not isinstance(reasons, list):
        reasons = []

    if priority not in {"low", "medium", "high"}:
        raise ExecutorError(f"decision.priority must be one of low|medium|high (got {priority!r})")

    if not risk_bucket:
        # keep tolerant but explicit default
        risk_bucket = "U"

    try:
        confidence_f = float(confidence)
    except Exception:
        confidence_f = 0.0

    return PolicyDecision(
        policy_id=str(policy_id),
        priority=priority,
        risk_bucket=risk_bucket,
        confidence=confidence_f,
        reasons=[str(x) for x in reasons],
    )


# -------------------------
# Plan builder
# -------------------------
def _build_actions(decision: PolicyDecision, payload_doc: Dict[str, Any], execute: bool) -> List[Dict[str, Any]]:
    stats = _extract_scan_stats(payload_doc)
    dry_run = (not execute)

    common_ctx = {
        "dry_run": dry_run,
        "inputs": {
            "files_scanned": stats.get("files_scanned"),
            "total_size_bytes": stats.get("total_size_bytes"),
            "eii_score_value": stats.get("eii_score_value"),
            "eii_grade": stats.get("eii_grade"),
        },
    }

    if decision.priority == "low":
        return [
            {
                "id": "report.only",
                "type": "report",
                "title": "Generate report only (no changes).",
                **common_ctx,
            }
        ]

    if decision.priority == "medium":
        return [
            {
                "id": "report.summary",
                "type": "report",
                "title": "Generate report + recommendations.",
                **common_ctx,
            },
            {
                "id": "propose.cleanup",
                "type": "proposal",
                "title": "Propose cleanup plan (no execution).",
                **common_ctx,
            },
        ]

    # high
    return [
        {
            "id": "report.summary",
            "type": "report",
            "title": "Generate report + recommendations.",
            **common_ctx,
        },
        {
            "id": "propose.cleanup",
            "type": "proposal",
            "title": "Propose cleanup plan.",
            **common_ctx,
        },
        {
            "id": "execute.cleanup",
            "type": "execution",
            "title": "Execute cleanup actions (guarded).",
            "dry_run": dry_run,
            "guardrails": {
                "require_user_confirm": True,
                "max_delete_percent": 5,
            },
            "inputs": common_ctx["inputs"],
        },
    ]


def build_execution_plan(policy_doc: Dict[str, Any], payload_doc: Dict[str, Any], execute: bool) -> Dict[str, Any]:
    decision = _parse_policy_decision(policy_doc)

    payload_schema = str(payload_doc.get("schema_id", ""))
    if payload_schema != "scan-payload":
        raise ExecutorError(f"Unexpected payload schema_id: {payload_schema!r} (expected 'scan-payload')")

    actions = _build_actions(decision, payload_doc, execute=execute)

    out: Dict[str, Any] = {
        "schema_id": "execution-plan",
        "schema_version": "v1.1",
        "generated_at": _utc_now(),
        "data_source": "local_pipeline",
        "decision_snapshot": {
            "policy_id": decision.policy_id,
            "priority": decision.priority,
            "risk_bucket": decision.risk_bucket,
            "confidence": decision.confidence,
            "reasons": decision.reasons,
        },
        "payload_snapshot": {
            "schema_id": payload_schema,
            "schema_version": payload_doc.get("schema_version"),
            "kpis": _extract_scan_stats(payload_doc),
        },
        "plan": actions,
        "audit": {
            "execute": bool(execute),
            "dry_run": (not execute),
            "notes": [
                "Executor v1.1 accepts policy_id at root OR decision.policy_id OR policy.policy_id.",
                "Plan is always generated (actions depend on priority).",
            ],
        },
    }
    return out


# -------------------------
# CLI
# -------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, help="Path to policy_decision.json")
    ap.add_argument("--payload", required=True, help="Path to scan_payload.json")
    ap.add_argument("--out", required=True, help="Output path for execution_plan.json")
    ap.add_argument("--execute", action="store_true", help="If set, plan is marked executable (dry_run=false).")
    args = ap.parse_args()

    policy_doc = _read_json(Path(args.policy))
    payload_doc = _read_json(Path(args.payload))

    plan = build_execution_plan(policy_doc, payload_doc, execute=bool(args.execute))
    _write_json(Path(args.out), plan)
    print(f"OK -> wrote: {args.out}")


if __name__ == "__main__":
    main()
