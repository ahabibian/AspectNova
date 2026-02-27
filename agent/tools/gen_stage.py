from __future__ import annotations
import sys
from pathlib import Path

# IMPORTANT:
# Do NOT use str.format() on templates that contain { } (dict/JSON).
# We use a simple token replacement instead.
TOKEN_STAGE = "__STAGE__"
TOKEN_STAGE_UPPER = "__STAGE_UPPER__"

T_MOD = r'''import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _read_json_bom_safe(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def run(run_id: str, out_dir: Path, inputs: dict, policy_path: Path) -> dict:
    """
    Implement stage logic here.
    Must return a report dict with:
      report["summary"]["status"] and report["status"] == report["summary"]["status"]
    """
    generated_at = datetime.now(timezone.utc).isoformat()

    results = []  # list of action/result dicts

    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = sum(1 for r in results if r.get("status") != "OK")

    summary = {
      "status": "PASS" if fail == 0 else "FAIL",
      "actions_total": len(results),
      "actions_ok": ok,
      "actions_fail": fail
    }

    report = {
      "contract_version": "__STAGE__/1.0",
      "schema_version": "1.0.0",
      "run_id": run_id,
      "generated_at_utc": generated_at,
      "inputs": inputs,
      "policy": str(policy_path),
      "results": results,
      "summary": summary
    }
    report["status"] = report["summary"]["status"]
    return report
'''

T_RUNNER = r'''from pathlib import Path
import sys
import json
from stages.__STAGE__.stage import run

def main():
    if len(sys.argv) < 2:
        print("usage: python .\\run___STAGE___stage.py <run_id>")
        raise SystemExit(2)

    run_id = sys.argv[1]
    out_dir = Path("runs") / run_id / "output" / "evidence"
    policy = Path("policies") / "__STAGE__.policy.json"

    inputs = {
        "note": "wire real inputs here"
    }

    report = run(run_id=run_id, out_dir=out_dir, inputs=inputs, policy_path=policy)

    out_path = out_dir / "__STAGE__.report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("__STAGE_UPPER__ STAGE DONE:", {"out": str(out_path), "status": report.get("status")})

if __name__ == "__main__":
    main()
'''

T_GATE = r'''import json
import sys
from pathlib import Path

def _read_json_bom_safe(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def fail(obj, code=1):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)

def main():
    if len(sys.argv) < 3:
        fail({"error":"usage","example":"python .\\tools\\gate___STAGE__.py <report.json> <policy.json>"}, 2)

    report_path = Path(sys.argv[1])
    policy_path = Path(sys.argv[2])

    report = _read_json_bom_safe(report_path)
    policy = _read_json_bom_safe(policy_path)
    req = policy.get("requirements") or {}

    reasons = []
    summary = (report.get("summary") or {})
    summary_status = str(summary.get("status") or "FAIL").upper()

    if report.get("status") != summary.get("status"):
        reasons.append({"type":"status_mismatch","detail":{"report.status": report.get("status"), "summary.status": summary.get("status")}})

    if summary_status not in ("PASS","FAIL"):
        reasons.append({"type":"invalid_summary_status","detail":{"got": summary.get("status")}})

    min_actions = int(req.get("min_actions", 0))
    actions_total = int(summary.get("actions_total") or 0)
    if actions_total < min_actions:
        reasons.append({"type":"min_actions_fail","detail":{"min":min_actions,"got": actions_total}})

    gate_status = "PASS" if (len(reasons) == 0 and summary_status == "PASS") else "FAIL"

    out = {
      "stage": "__STAGE__",
      "policy_version": policy.get("policy_version"),
      "status": gate_status,
      "reasons": reasons,
      "inputs": {"report": str(report_path), "policy": str(policy_path)},
      "summary": {"summary_status": summary.get("status"), "actions_total": actions_total}
    }

    if gate_status == "PASS":
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    fail(out, 1)

if __name__ == "__main__":
    main()
'''

T_POLICY = r'''{
  "policy_version": "1.0.0",
  "requirements": {
    "min_actions": 0
  }
}
'''

def _apply_tokens(s: str, stage: str) -> str:
    return (
        s.replace("__STAGE__", stage)
         .replace("__STAGE_UPPER__", stage.upper())
         .replace("run___STAGE___stage.py", f"run_{stage}_stage.py")
         .replace("gate___STAGE__.py", f"gate_{stage}.py")
    )

def main():
    if len(sys.argv) < 2:
        print("usage: python .\\tools\\gen_stage.py <stage_name>")
        raise SystemExit(2)

    stage = sys.argv[1].strip().lower().replace("-", "_")
    root = Path(".")
    stage_dir = root / "stages" / stage
    tools_dir = root / "tools"
    pol_dir = root / "policies"

    stage_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    pol_dir.mkdir(parents=True, exist_ok=True)

    (root / "stages" / "__init__.py").write_text("", encoding="utf-8")
    (stage_dir / "__init__.py").write_text("", encoding="utf-8")

    (stage_dir / "stage.py").write_text(_apply_tokens(T_MOD, stage), encoding="utf-8")
    (root / f"run_{stage}_stage.py").write_text(_apply_tokens(T_RUNNER, stage), encoding="utf-8")
    (tools_dir / f"gate_{stage}.py").write_text(_apply_tokens(T_GATE, stage), encoding="utf-8")
    (pol_dir / f"{stage}.policy.json").write_text(T_POLICY, encoding="utf-8")

    print("OK:", stage)

if __name__ == "__main__":
    main()