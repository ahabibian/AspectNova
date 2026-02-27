from __future__ import annotations

import json
import sys
from pathlib import Path

def _read_json_bom_safe(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _safe_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return int(default)

def fail(obj, code=1):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)

def main():
    if len(sys.argv) < 2:
        fail({"error":"usage","example":"python .\\tools\\gate_execution.py <execution_report.json> [policy.json]"}, 2)

    report_path = Path(sys.argv[1])
    policy_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None

    if not report_path.exists():
        fail({
            "stage": "execution",
            "status": "FAIL",
            "reasons": [{"type":"missing_execution_report","detail":{"path": str(report_path)}}],
            "inputs": {"execution_report": str(report_path), "policy": str(policy_path) if policy_path else None}
        }, 1)

    report = _read_json_bom_safe(report_path)
    policy = _read_json_bom_safe(policy_path) if (policy_path and policy_path.exists()) else {"policy_version":"1.0.0","requirements":{}}
    req = policy.get("requirements") or {}

    reasons = []

    summary = report.get("summary") or {}
    status = (summary.get("status") or report.get("status") or "FAIL")

    # enforce rule: report.status == report.summary.status (if both exist)
    if (report.get("status") is not None) and (summary.get("status") is not None) and (report.get("status") != summary.get("status")):
        reasons.append({"type":"status_mismatch","detail":{"report.status": report.get("status"), "summary.status": summary.get("status")}})

    status_u = str(status).upper()
    if status_u not in ("PASS","FAIL"):
        reasons.append({"type":"invalid_status","detail":{"got": status}})

    # ---- Determine whether actions are expected by reading command_plan.json (if present)
    evidence_dir = report_path.parent
    plan_path = evidence_dir / "command_plan.json"
    plan_actions = None
    findings = None
    verdict_status = None

    if plan_path.exists():
        try:
            plan = _read_json_bom_safe(plan_path)
            plan_actions_list = plan.get("actions") or []
            plan_actions = len(plan_actions_list) if isinstance(plan_actions_list, list) else 0
            ps = plan.get("summary") or {}
            findings = _safe_int(ps.get("findings") or 0, 0)
            verdict_status = ps.get("verdict_status")
        except Exception as e:
            reasons.append({"type":"command_plan_read_error","detail":{"path": str(plan_path), "error": str(e)}})

    # minimum actions:
    # - If command_plan exists and has 0 actions, it's valid for execution to have 0 actions.
    # - Only enforce policy.min_actions when the plan had actions to execute.
    min_actions = _safe_int(req.get("min_actions", 0), 0)
    actions_total = _safe_int(summary.get("actions_total") or 0, 0)

    min_actions_effective = min_actions
    if plan_actions is not None and plan_actions == 0:
        min_actions_effective = 0

    if actions_total < min_actions_effective:
        reasons.append({"type":"min_actions_fail","detail":{"min": min_actions_effective, "got": actions_total, "policy_min": min_actions, "plan_actions": plan_actions}})

    gate_status = "PASS" if (len(reasons) == 0 and status_u == "PASS") else "FAIL"

    out = {
        "stage": "execution",
        "policy_version": policy.get("policy_version"),
        "status": gate_status,
        "reasons": reasons,
        "inputs": {
            "execution_report": str(report_path).replace("/", "\\"),
            "policy": str(policy_path).replace("/", "\\") if policy_path else None,
            "command_plan": str(plan_path).replace("/", "\\") if plan_path.exists() else None
        },
        "summary": {
            "execution_status": summary.get("status"),
            "actions_total": actions_total,
            "actions_ok": _safe_int(summary.get("actions_ok") or 0, 0),
            "actions_fail": _safe_int(summary.get("actions_fail") or 0, 0),
            "plan_actions": plan_actions,
            "findings": findings,
            "verdict_status": verdict_status
        }
    }

    if gate_status == "PASS":
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    fail(out, 1)

if __name__ == "__main__":
    main()