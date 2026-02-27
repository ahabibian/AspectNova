from __future__ import annotations

import json
import sys
from pathlib import Path

def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return float(default)

def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python tools/gate_verdict.py <verdict.json> <policy.json>")
        return 2

    verdict_path = Path(sys.argv[1])
    pol_path = Path(sys.argv[2])

    if not verdict_path.exists():
        print(json.dumps({
            "stage": "verdict",
            "policy_version": "unknown",
            "status": "FAIL",
            "reasons": [{"type": "missing_verdict_artifact", "detail": {"path": str(verdict_path)}}],
            "inputs": {"verdict": str(verdict_path), "policy": str(pol_path)}
        }, indent=2))
        return 1

    policy = _read_json(pol_path) if pol_path.exists() else {"policy_version": "unknown", "requirements": {}}
    v = _read_json(verdict_path)

    req = policy.get("requirements") or {}
    max_owner_fail_rate = _num(req.get("max_owner_fail_rate", 0.005), 0.005)
    max_access_denied = int(req.get("max_access_denied", 0))
    max_other_error = int(req.get("max_other_error", 0))

    # verdict.json schema (your file):
    # v["summary"]["totals"] has owner_ok/owner_fail/owner_fail_rate
    totals = ((v.get("summary") or {}).get("totals") or {})
    owner_ok = int(totals.get("owner_ok", 0))
    owner_fail = int(totals.get("owner_fail", 0))

    # Prefer explicit owner_fail_rate if present, else compute
    if "owner_fail_rate" in totals:
        owner_fail_rate = _num(totals.get("owner_fail_rate", 0.0), 0.0)
    else:
        denom = (owner_ok + owner_fail) if (owner_ok + owner_fail) > 0 else 1
        owner_fail_rate = owner_fail / denom

    # Optional fields (might not exist in verdict.json yet)
    access_denied = int(totals.get("access_denied", 0))
    other_error = int(totals.get("other_error", 0))
    findings = v.get("findings") or []
    findings_count = len(findings) if isinstance(findings, list) else 0

    reasons = []
    if owner_fail_rate > max_owner_fail_rate:
        reasons.append({"type": "max_owner_fail_rate", "detail": {"max": max_owner_fail_rate, "got": owner_fail_rate}})
    if access_denied > max_access_denied:
        reasons.append({"type": "max_access_denied", "detail": {"max": max_access_denied, "got": access_denied}})
    if other_error > max_other_error:
        reasons.append({"type": "max_other_error", "detail": {"max": max_other_error, "got": other_error}})

    status = "PASS" if not reasons else "FAIL"
    out = {
        "stage": "verdict",
        "policy_version": policy.get("policy_version", policy.get("version", "unknown")),
        "status": status,
        "reasons": reasons,
        "inputs": {
            "verdict": str(verdict_path).replace("/", "\\"),
            "policy": str(pol_path).replace("/", "\\"),
        },
        "summary": {
            "owner_fail_rate": owner_fail_rate,
            "access_denied": access_denied,
            "other_error": other_error,
            "findings": findings_count
        }
    }
    print(json.dumps(out, indent=2))
    return 0 if status == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())