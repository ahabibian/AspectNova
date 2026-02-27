from __future__ import annotations

import json
import sys
from pathlib import Path


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python tools/gate_owner_report.py <owner_report_or_stats.json> <policy.json>")
        return 2

    report_path = Path(sys.argv[1])
    pol_path = Path(sys.argv[2])

    if not report_path.exists():
        print(json.dumps({
            "stage": "owner_enricher",
            "policy_version": "unknown",
            "status": "FAIL",
            "reasons": [{"type": "missing_owner_artifact", "detail": {"path": str(report_path)}}],
            "inputs": {"artifact": str(report_path), "policy": str(pol_path)}
        }, indent=2))
        return 1

    policy = _read_json(pol_path)
    rep = _read_json(report_path)

    # support BOTH policy formats:
    # A) new: policy["requirements"]["max_owner_fail_rate"]
    # B) old: policy["rules"]["max_fail_rate"]
    req = (policy.get("requirements") or {})
    rules = (policy.get("rules") or {})

    max_fail_rate = req.get("max_owner_fail_rate", rules.get("max_fail_rate", 0.005))
    max_access_denied = req.get("max_access_denied", rules.get("max_access_denied", 0))
    max_other_error = req.get("max_other_error", rules.get("max_other_error", 0))

    # normalize report/stats formats
    if "totals" in rep and isinstance(rep["totals"], dict):
        totals = rep["totals"]
        ok = int(totals.get("ok", 0))
        fail = int(totals.get("fail", 0))
        not_found = int(totals.get("not_found", 0))
        access_denied = int(totals.get("access_denied", 0))
        other_error = int(totals.get("other_error", 0))
    elif "owner_lookup" in rep and isinstance(rep["owner_lookup"], dict):
        ol = rep["owner_lookup"]
        ok = int(ol.get("ok", 0))
        fail = int(ol.get("fail", 0))
        not_found = int(ol.get("not_found", 0))
        access_denied = int(ol.get("access_denied", 0))
        other_error = int(ol.get("other_error", 0))
    else:
        print(json.dumps({
            "stage": "owner_enricher",
            "policy_version": policy.get("policy_version", policy.get("version", "unknown")),
            "status": "FAIL",
            "reasons": [{"type": "unrecognized_owner_artifact_schema", "detail": {"keys": sorted(list(rep.keys()))}}],
            "inputs": {"artifact": str(report_path).replace("/", "\\"), "policy": str(pol_path).replace("/", "\\")}
        }, indent=2))
        return 1

    denom = (ok + fail) if (ok + fail) > 0 else 1
    owner_fail_rate = fail / denom

    reasons = []
    if owner_fail_rate > float(max_fail_rate):
        reasons.append({"type": "max_owner_fail_rate", "detail": {"max": max_fail_rate, "got": owner_fail_rate}})
    if access_denied > int(max_access_denied):
        reasons.append({"type": "max_access_denied", "detail": {"max": max_access_denied, "got": access_denied}})
    if other_error > int(max_other_error):
        reasons.append({"type": "max_other_error", "detail": {"max": max_other_error, "got": other_error}})

    status = "PASS" if not reasons else "FAIL"

    out = {
        "stage": "owner_enricher",
        "policy_version": policy.get("policy_version", policy.get("version", "unknown")),
        "status": status,
        "reasons": reasons,
        "inputs": {"artifact": str(report_path).replace("/", "\\"), "policy": str(pol_path).replace("/", "\\")},
        "summary": {
            "owner_fail_rate": owner_fail_rate,
            "ok": ok,
            "fail": fail,
            "not_found": not_found,
            "access_denied": access_denied,
            "other_error": other_error
        }
    }
    print(json.dumps(out, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
