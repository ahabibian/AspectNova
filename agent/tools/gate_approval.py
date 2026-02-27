import json
import sys
from pathlib import Path


def _read_json_bom_safe(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def fail(obj, code=1):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def main():
    if len(sys.argv) < 3:
        fail({"error": "usage", "example": "python .\\tools\\gate_approval.py <approval.json> <policy.json>"}, 2)

    approval_path = Path(sys.argv[1])
    policy_path = Path(sys.argv[2])

    approval = _read_json_bom_safe(approval_path)
    policy = _read_json_bom_safe(policy_path)
    req = policy.get("requirements") or {}

    reasons = []

    # 1) upstream gate
    require_upstream_ok = bool(req.get("require_upstream_ok", False))
    upstream_ok = bool((approval.get("upstream") or {}).get("upstream_ok"))
    if require_upstream_ok and not upstream_ok:
        reasons.append({"type": "upstream_not_ok", "detail": {"require_upstream_ok": True, "got": upstream_ok}})

    # 2) decision
    require_decision = (req.get("require_decision") or "").strip().upper()
    got_decision = ((approval.get("decision") or {}).get("status") or "").strip().upper()
    if require_decision and got_decision != require_decision:
        reasons.append({"type": "decision_mismatch", "detail": {"require": require_decision, "got": got_decision}})

    # 3) hashes present
    require_hashes = bool(req.get("require_hashes", False))
    integrity = approval.get("integrity") or {}
    needed = ["command_plan", "command_plan_gate", "run_manifest", "verdict"]
    missing_hash = []
    for k in needed:
        sha = ((integrity.get(k) or {}).get("sha256"))
        if not sha or not isinstance(sha, str) or len(sha) < 32:
            missing_hash.append(k)
    if require_hashes and missing_hash:
        reasons.append({"type": "missing_hashes", "detail": {"missing": missing_hash}})

    status = "PASS" if not reasons else "FAIL"

    out = {
        "stage": "approval",
        "policy_version": policy.get("policy_version"),
        "status": status,
        "reasons": reasons,
        "inputs": {"approval": str(approval_path), "policy": str(policy_path)},
        "summary": {
            "decision": got_decision,
            "upstream_ok": upstream_ok
        }
    }

    if status == "PASS":
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    fail(out, 1)


if __name__ == "__main__":
    main()
