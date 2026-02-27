from __future__ import annotations

import json
import sys
from pathlib import Path

def _read_json_bom_safe(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def fail(obj, code=1):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)

def main() -> int:
    if len(sys.argv) < 3:
        fail({"error":"usage","example":"python .\\tools\\gate_command_plan.py <command_plan.json> <policy.json>"}, 2)

    plan_path = Path(sys.argv[1])
    policy_path = Path(sys.argv[2])

    if not plan_path.exists():
        fail({
            "stage":"command_plan",
            "policy_version":"unknown",
            "status":"FAIL",
            "reasons":[{"type":"missing_plan_artifact","detail":{"path":str(plan_path)}}],
            "inputs":{"plan":str(plan_path), "policy":str(policy_path)}
        }, 1)

    plan = _read_json_bom_safe(plan_path)
    policy = _read_json_bom_safe(policy_path) if policy_path.exists() else {"policy_version":"unknown","requirements":{}}
    req = policy.get("requirements") or {}

    actions = plan.get("actions") or []
    if not isinstance(actions, list):
        actions = []

    summary = plan.get("summary") or {}
    findings = int(summary.get("findings") or 0)

    # IMPORTANT:
    # - If findings == 0 and verdict_status == PASS, it's valid for actions to be empty.
    # - Only enforce min_actions when there is something to act on (findings > 0).
    min_actions = int(req.get("min_actions", 0))
    min_actions_effective = 0 if findings == 0 else min_actions

    reasons = []
    if len(actions) < min_actions_effective:
        reasons.append({"type":"min_actions_fail","detail":{"min":min_actions_effective,"got":len(actions)}})

    fail_rate = _num(summary.get("owner_fail_rate", 0.0), 0.0)
    max_fail_rate = _num(req.get("max_owner_fail_rate", 0.0), 0.0)
    if fail_rate > max_fail_rate:
        reasons.append({"type":"max_owner_fail_rate","detail":{"max":max_fail_rate,"got":fail_rate}})

    requires_approval = sum(1 for a in actions if isinstance(a, dict) and a.get("requires_approval"))
    max_req_approval = int(req.get("max_requires_approval", 0))
    if requires_approval > max_req_approval:
        reasons.append({"type":"max_requires_approval","detail":{"max":max_req_approval,"got":requires_approval}})

    status = "PASS" if not reasons else "FAIL"
    out = {
        "stage": "command_plan",
        "policy_version": policy.get("policy_version"),
        "status": status,
        "reasons": reasons,
        "inputs": {"plan": str(plan_path).replace("/", "\\"), "policy": str(policy_path).replace("/", "\\")},
        "counts": {"actions": len(actions), "requires_approval": requires_approval},
        "summary": {
            "owner_fail_rate": fail_rate,
            "verdict_status": summary.get("verdict_status"),
            "findings": findings
        }
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())