from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

def _read_json_bom_safe(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _now_utc():
    return datetime.now(timezone.utc).isoformat()

def _action_type(a: dict) -> str:
    # tolerate both "type" or nested structures
    t = a.get("type")
    if t:
        return str(t)
    if isinstance(a.get("action"), dict) and a["action"].get("type"):
        return str(a["action"]["type"])
    return "UNKNOWN"

def execute_plan(run_id: str, out_dir: Path, plan_path: Path, approval_path: Path | None = None) -> dict:
    plan = _read_json_bom_safe(plan_path)
    approval = _read_json_bom_safe(approval_path) if (approval_path and approval_path.exists()) else None

    actions = plan.get("actions") or []
    results = []

    # If approval exists, we can optionally enforce it. For now, we trust upstream gating already.
    approved = True
    if approval is not None:
        dec = ((approval.get("decision") or {}).get("status") or approval.get("decision") or "APPROVE")
        approved = str(dec).upper() == "APPROVE"

    for a in actions:
        aid = a.get("action_id") or a.get("id") or "ACT:UNKNOWN"
        atype = _action_type(a)
        req_app = bool(a.get("requires_approval"))

        # --- policy: plan-only safe actions should never fail execution
        if atype in ("recommendation", "verify_or_rescan"):
            results.append({
                "id": aid,
                "type": atype,
                "status": "OK",
                "detail": {"note": "Plan-only action recorded; no destructive execution performed."}
            })
            continue

        # Unknown but non-approved-required actions: keep it safe and non-failing
        if (atype == "UNKNOWN") and (not req_app):
            results.append({
                "id": aid,
                "type": atype,
                "status": "OK",
                "detail": {"note": "Unknown action type but does not require approval; recorded as OK (no-op)."}
            })
            continue

        # Actions requiring approval must be explicitly approved
        if req_app and not approved:
            results.append({
                "id": aid,
                "type": atype,
                "status": "FAIL",
                "detail": {"error": "requires_approval_but_not_approved"}
            })
            continue

        # Default: we are not implementing real execution in this run; mark as SKIPPED_OK unless explicitly executable
        results.append({
            "id": aid,
            "type": atype,
            "status": "OK",
            "detail": {"note": "Execution engine running in plan-only mode; action treated as OK/no-op."}
        })

    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = sum(1 for r in results if r.get("status") != "OK")

    summary = {
        "status": "PASS" if fail == 0 else "FAIL",
        "actions_total": len(results),
        "actions_ok": ok,
        "actions_fail": fail
    }

    report = {
        "contract_version": "execution/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": _now_utc(),
        "mode": "plan_only",
        "inputs": {
            "command_plan": str(plan_path),
            "approval": str(approval_path) if approval_path else None
        },
        "environment": {},
        "results": results,
        "summary": summary
    }
    report["status"] = report["summary"]["status"]
    return report

def run(run_id: str, out_dir: Path) -> dict:
    plan_path = out_dir / "command_plan.json"
    approval_path = out_dir / "approval.json"
    rep = execute_plan(run_id=run_id, out_dir=out_dir, plan_path=plan_path, approval_path=approval_path)
    out_path = out_dir / "execution_report.json"
    _write_json(out_path, rep)
    return {"out": str(out_path), "status": rep.get("status"), "actions": int((rep.get("summary") or {}).get("actions_total") or 0)}
