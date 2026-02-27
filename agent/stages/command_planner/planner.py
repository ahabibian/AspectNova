import json
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

def build_command_plan(run_id: str, verdict_path: Path, policy_path: Path, out_dir: Path):
    verdict = _read_json_bom_safe(verdict_path)
    policy  = _read_json_bom_safe(policy_path)
    _ = policy.get("requirements") or {}  # reserved for future mapping rules

    generated_at = datetime.now(timezone.utc).isoformat()

    findings = verdict.get("findings") or []
    summary  = verdict.get("summary") or {}
    totals   = (summary.get("totals") or {})
    fail_by_code = summary.get("fail_by_code") or {}

    actions = []

    for f in findings:
        fid = f.get("id")
        sev = (f.get("severity") or "LOW").upper()

        if fid == "F-OWNER-NOT-FOUND":
            samples = f.get("samples") or []
            for s in samples:
                actions.append({
                    "action_id": f"ACT:{fid}:{_sha1(str(s))[:10]}",
                    "type": "verify_or_rescan",
                    "target": {"path_abs": s},
                    "justification": {"finding_id": fid, "severity": sev},
                    "risk": {"level": "LOW", "reason": "File present at scan time but missing at enrich time; no destructive operation."},
                    "requires_approval": False,
                    "dry_run_preview": {"note": "Re-scan same root; compare deltas; in strict runs snapshot/lock before enrich."}
                })

            actions.append({
                "action_id": f"ACT:{fid}:STRICT-MODE",
                "type": "recommendation",
                "target": {"scope": "run"},
                "justification": {"finding_id": fid, "severity": sev},
                "risk": {"level": "LOW", "reason": "Process hardening suggestion."},
                "requires_approval": False,
                "dry_run_preview": {"note": "Strict runs: re-scan immediately before enrich OR use snapshotting/VSS."}
            })
        else:
            actions.append({
                "action_id": f"ACT:{fid or 'UNKNOWN'}:{_sha1(json.dumps(f,sort_keys=True))[:10]}",
                "type": "review",
                "target": {"scope": "run"},
                "justification": {"finding_id": fid or "UNKNOWN", "severity": sev},
                "risk": {"level": "LOW", "reason": "Unmapped finding -> manual review."},
                "requires_approval": True,
                "dry_run_preview": {"note": "Define deterministic mapping for this finding before any execution stage."}
            })

    plan = {
        "contract_version": "command_plan/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "inputs": {
            "verdict": str(verdict_path),
            "policy": str(policy_path),
            "evidence_pack": ((verdict.get("inputs") or {}).get("evidence_pack"))
        },
        "summary": {
            "verdict_status": (summary.get("status") or "UNKNOWN"),
            "owner_fail_rate": float(totals.get("owner_fail_rate") or 1.0),
            "fail_by_code": fail_by_code,
            "findings": len(findings),
            "actions": len(actions)
        },
        "actions": actions
    }

    out_plan = out_dir / "command_plan.json"
    _write_json(out_plan, plan)

    report = {
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "status": "PASS",
        "totals": {
            "findings": len(findings),
            "actions": len(actions),
            "requires_approval": sum(1 for a in actions if a.get("requires_approval"))
        },
        "action_type_top": {},
        "owner_fail_rate": float(totals.get("owner_fail_rate") or 1.0),
        "fail_by_code": fail_by_code
    }

    for a in actions:
        t = a.get("type") or "UNKNOWN"
        report["action_type_top"][t] = report["action_type_top"].get(t, 0) + 1

    _write_json(out_dir / "command_plan.report.json", report)
    _write_json(out_dir / "command_plan.sample.json", {
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "plan_path": str(out_plan),
        "actions_sample": actions[:10]
    })

    return {"out": str(out_plan), "report": str(out_dir / "command_plan.report.json"), "actions": len(actions)}
