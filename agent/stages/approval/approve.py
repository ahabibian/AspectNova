import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import os
import platform


def _read_json_bom_safe(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def build_approval(run_id: str, base_evidence_dir: Path, decision: str = "APPROVE", reason: str | None = None):
    """
    Inputs (must exist):
      - command_plan.json
      - command_plan.gate.json
      - run_manifest.json
      - verdict.json (for traceability)
    Outputs:
      - approval.json
      - approval.report.json
      - approval.sample.json
    """

    generated_at = datetime.now(timezone.utc).isoformat()

    plan_path = base_evidence_dir / "command_plan.json"
    plan_gate_path = base_evidence_dir / "command_plan.gate.json"
    manifest_path = base_evidence_dir / "run_manifest.json"
    verdict_path = base_evidence_dir / "verdict.json"

    missing = [str(p) for p in [plan_path, plan_gate_path, manifest_path, verdict_path] if not p.exists()]
    if missing:
        raise FileNotFoundError("missing required inputs: " + ", ".join(missing))

    plan = _read_json_bom_safe(plan_path)
    plan_gate = _read_json_bom_safe(plan_gate_path)
    manifest = _read_json_bom_safe(manifest_path)
    verdict = _read_json_bom_safe(verdict_path)

    # hard requirement: upstream gate PASS
    upstream_ok = (plan_gate.get("status") == "PASS")

    decision_norm = (decision or "APPROVE").strip().upper()
    if decision_norm not in ("APPROVE", "REJECT"):
        raise ValueError("decision must be APPROVE or REJECT")

    # build integrity set (deterministic)
    integrity = {
        "command_plan": {
            "path": str(plan_path),
            "sha256": _sha256_file(plan_path)
        },
        "command_plan_gate": {
            "path": str(plan_gate_path),
            "sha256": _sha256_file(plan_gate_path),
            "status": plan_gate.get("status")
        },
        "run_manifest": {
            "path": str(manifest_path),
            "sha256": _sha256_file(manifest_path)
        },
        "verdict": {
            "path": str(verdict_path),
            "sha256": _sha256_file(verdict_path),
            "status": (verdict.get("summary") or {}).get("status")
        }
    }

    # approver identity (local, non-sensitive)
    approver = {
        "type": "local_user",
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
        "machine": platform.node() or "unknown",
        "os": platform.platform()
    }

    approval = {
        "contract_version": "approval/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "inputs": {
            "command_plan": str(plan_path),
            "command_plan_gate": str(plan_gate_path),
            "run_manifest": str(manifest_path),
            "verdict": str(verdict_path)
        },
        "upstream": {
            "command_plan_gate_status": plan_gate.get("status"),
            "upstream_ok": bool(upstream_ok)
        },
        "decision": {
            "status": decision_norm,   # APPROVE/REJECT
            "reason": reason
        },
        "approver": approver,
        "integrity": integrity,
        "summary": {
            "actions": int((plan.get("summary") or {}).get("actions") or len(plan.get("actions") or [])),
            "requires_approval": int((plan.get("summary") or {}).get("requires_approval") or 0),
            "findings": int((plan.get("summary") or {}).get("findings") or 0),
            "owner_fail_rate": float((plan.get("summary") or {}).get("owner_fail_rate") or 1.0)
        }
    }

    out_approval = base_evidence_dir / "approval.json"
    _write_json(out_approval, approval)

    report = {
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "status": "PASS",
        "decision": decision_norm,
        "upstream_ok": bool(upstream_ok),
        "inputs_ok": True,
        "hashes_present": True,
        "actions": approval["summary"]["actions"],
        "requires_approval": approval["summary"]["requires_approval"]
    }
    _write_json(base_evidence_dir / "approval.report.json", report)

    sample = {
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "decision": approval["decision"],
        "integrity_sample": {
            "command_plan_sha256": integrity["command_plan"]["sha256"],
            "verdict_sha256": integrity["verdict"]["sha256"]
        }
    }
    _write_json(base_evidence_dir / "approval.sample.json", sample)

    return {"out": str(out_approval), "report": str(base_evidence_dir / "approval.report.json"), "decision": decision_norm, "upstream_ok": bool(upstream_ok)}
