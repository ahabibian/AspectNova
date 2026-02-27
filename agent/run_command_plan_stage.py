from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _write(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python .\\run_command_plan_stage.py <run_id>")
        return 2

    run_id = sys.argv[1]
    root = Path("runs") / run_id
    out_dir = root / "output" / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    verdict_path = out_dir / "verdict.json"
    if not verdict_path.exists():
        print(json.dumps({"status":"FAIL","where":"command_plan","reason":"missing_verdict","path":str(verdict_path)}, indent=2))
        return 1

    verdict = _read(verdict_path)

    totals = ((verdict.get("summary") or {}).get("totals") or {})
    owner_fail_rate = _num(totals.get("owner_fail_rate", 0.0), 0.0)

    findings = verdict.get("findings") or []
    findings_count = len(findings) if isinstance(findings, list) else 0

    verdict_status = ((verdict.get("summary") or {}).get("status") or "UNKNOWN")

    # Build actions:
    # - If findings_count == 0: no actions needed (valid)
    # - Else: create placeholder review actions (safe default)
    actions = []
    if findings_count > 0 and isinstance(findings, list):
        for i, f in enumerate(findings, start=1):
            # tolerate unknown finding schema
            fp = None
            if isinstance(f, dict):
                fp = f.get("path") or f.get("asset_path") or f.get("target") or f.get("file")
            actions.append({
                "id": f"act_{i:04d}",
                "type": "review",
                "target_path": fp,
                "reason": "Finding requires review",
                "requires_approval": True
            })

    now = datetime.now(timezone.utc).isoformat()

    plan = {
        "contract_version": "command_plan/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": now,
        "summary": {
            "verdict_status": verdict_status,
            "findings": findings_count,
            "owner_fail_rate": owner_fail_rate
        },
        "actions": actions
    }

    report = {
        "run_id": run_id,
        "generated_at_utc": now,
        "actions": len(actions),
        "requires_approval": sum(1 for a in actions if a.get("requires_approval")),
        "note": "If findings==0, actions may be empty (valid)."
    }

    sample = {
        "example_action": {
            "id": "act_0001",
            "type": "review",
            "target_path": "C:\\path\\to\\asset",
            "reason": "Finding requires review",
            "requires_approval": True
        }
    }

    out_plan = out_dir / "command_plan.json"
    out_report = out_dir / "command_plan.report.json"
    out_sample = out_dir / "command_plan.sample.json"

    _write(out_plan, plan)
    _write(out_report, report)
    _write(out_sample, sample)

    print("COMMAND PLAN STAGE DONE:", {"out": str(out_plan).replace("/", "\\"), "report": str(out_report).replace("/", "\\"), "actions": len(actions)})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())