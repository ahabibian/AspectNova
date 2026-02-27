import json, sys
from pathlib import Path

def _read_json_bom_safe(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def fail(obj, code=1):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)

def main():
    if len(sys.argv) < 3:
        fail({"error":"usage","example":"python .\\tools\\gate_manifest.py <manifest.report.json> <policy.json>"}, 2)

    rep_path = Path(sys.argv[1])
    pol_path = Path(sys.argv[2])

    rep = _read_json_bom_safe(rep_path)
    pol = _read_json_bom_safe(pol_path)
    req = pol.get("requirements") or {}

    reasons = []
    summ = rep.get("summary") or {}

    if rep.get("status") != summ.get("status"):
        reasons.append({"type":"status_mismatch","detail":{"report.status": rep.get("status"), "summary.status": summ.get("status")}})

    min_art = int(req.get("min_artifacts", 0))
    got_art = int(summ.get("artifact_count") or 0)
    if got_art < min_art:
        reasons.append({"type":"min_artifacts_fail","detail":{"min":min_art,"got":got_art}})

    gate = "PASS" if (len(reasons)==0 and str(summ.get("status") or "FAIL").upper()=="PASS") else "FAIL"

    out = {
        "stage":"manifest",
        "policy_version": pol.get("policy_version"),
        "status": gate,
        "reasons": reasons,
        "inputs": {"report": str(rep_path), "policy": str(pol_path)},
        "summary": {"report_status": rep.get("status"), "artifact_count": got_art}
    }

    if gate=="PASS":
        print(json.dumps(out, ensure_ascii=False, indent=2)); return
    fail(out, 1)

if __name__ == "__main__":
    main()
