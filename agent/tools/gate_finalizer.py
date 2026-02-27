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
        fail({"error":"usage","example":"python .\\tools\\gate_finalizer.py <final_report.json> <policy.json>"}, 2)

    report_path = Path(sys.argv[1])
    policy_path = Path(sys.argv[2])

    report = _read_json_bom_safe(report_path)
    policy = _read_json_bom_safe(policy_path)

    reasons = []
    summary = (report.get("summary") or {})
    s_status = str(summary.get("status") or "").upper()
    r_status = str(report.get("status") or "").upper()

    if report.get("status") != summary.get("status"):
        reasons.append({
            "type": "status_mismatch",
            "detail": {"report.status": report.get("status"), "summary.status": summary.get("status")}
        })

    if s_status not in ("PASS", "FAIL"):
        reasons.append({"type":"invalid_summary_status","detail":{"got": summary.get("status")}})

    # upstream must all be PASS for final PASS
    upstream_ok = bool(summary.get("upstream_all_pass"))
    if s_status == "PASS" and not upstream_ok:
        reasons.append({"type":"pass_but_upstream_not_all_pass","detail":{"upstream_all_pass": upstream_ok}})

    # policy: must-have gates exist in report checks
    req = (policy.get("requirements") or {})
    must = req.get("must_have_upstream_gates") or []
    gate_status = (((report.get("checks") or {}).get("upstream_gates") or {}).get("gate_status") or {})
    for k in must:
        if k not in gate_status:
            reasons.append({"type":"missing_upstream_gate_key","detail":{"missing": k}})

    gate = "PASS" if (len(reasons) == 0 and r_status == "PASS") else "FAIL"

    out = {
        "stage": "finalizer",
        "policy_version": policy.get("policy_version"),
        "status": gate,
        "reasons": reasons,
        "inputs": {"report": str(report_path), "policy": str(policy_path)},
        "summary": {
            "report_status": report.get("status"),
            "summary_status": summary.get("status"),
            "upstream_all_pass": summary.get("upstream_all_pass"),
            "actions_total": summary.get("actions_total")
        }
    }

    if gate == "PASS":
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    fail(out, 1)

if __name__ == "__main__":
    main()