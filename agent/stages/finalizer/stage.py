from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


def _read_json_bom_safe(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _write_json_no_bom(p: Path, obj: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for ch in iter(lambda: f.read(1024 * 1024), b""):
            h.update(ch)
    return h.hexdigest()


def _gate_status_from_file(gate_path: Path) -> str:
    if not gate_path.exists():
        return "MISSING"
    try:
        d = _read_json_bom_safe(gate_path)
        return str(d.get("status") or "UNKNOWN").upper()
    except Exception:
        return "UNREADABLE"


def _bool_all_pass(status_map: Dict[str, str]) -> bool:
    # consider PASS only as pass; anything else => fail
    return all(str(v).upper() == "PASS" for v in status_map.values())


def run(run_id: str, out_dir: Path, inputs: Dict[str, Any], policy_path: Path) -> Dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()

    # --- expected upstream gate files (paths relative to repo root)
    # Evidence pack gate lives next to evidence pack outputs
    gate_paths = {
        "evidence_pack": out_dir / "evidence_pack.gate.json",
        "verdict": out_dir / "verdict.gate.json",
        "command_plan": out_dir / "command_plan.gate.json",
        "approval": out_dir / "approval.gate.json",
        "execution": out_dir / "execution.gate.json",
        "integrity": out_dir / "integrity.gate.json",
    }

    upstream_gate_status = {k: _gate_status_from_file(p) for k, p in gate_paths.items()}

    # --- read run manifest if present (preferred), else build a minimal manifest snapshot
    manifest_path = out_dir / "run_manifest.json"
    manifest = None
    if manifest_path.exists():
        try:
            manifest = _read_json_bom_safe(manifest_path)
        except Exception:
            manifest = None

    if manifest is None:
        # fallback: compute hashes for common artifacts if they exist
        candidates = [
            out_dir / "evidence_pack.v1.json",
            out_dir / "evidence_pack.v1+owner.json",
            out_dir / "owner_enricher.report.json",
            out_dir / "verdict.json",
            out_dir / "command_plan.json",
            out_dir / "approval.json",
            out_dir / "execution_report.json",
            out_dir / "integrity_report.json",
        ]
        arts = []
        for p in candidates:
            if p.exists():
                arts.append({"path": str(p), "bytes": p.stat().st_size, "sha256": _sha256_file(p)})
        manifest = {
            "run_id": run_id,
            "generated_at_utc": generated_at,
            "artifacts": arts,
            "note": "fallback manifest (run_manifest.json missing or unreadable)"
        }

    # --- policy (optional now; reserved for strictness later)
    policy = {}
    if policy_path.exists():
        try:
            policy = _read_json_bom_safe(policy_path)
        except Exception:
            policy = {}

    # --- results: deterministic, auditable
    results: List[Dict[str, Any]] = []

    # Action 1: verify upstream gates
    all_pass = _bool_all_pass(upstream_gate_status)
    results.append({
        "id": "FINAL:UPSTREAM_GATES",
        "status": "OK" if all_pass else "FAIL",
        "detail": {"upstream_gate_status": upstream_gate_status}
    })

    # Action 2: ensure final report will be present (this action always OK because we are producing it)
    results.append({
        "id": "FINAL:REPORT_EMITTED",
        "status": "OK",
        "detail": {"out_dir": str(out_dir)}
    })

    # Action 3: embed manifest integrity snapshot
    results.append({
        "id": "FINAL:MANIFEST_EMBED",
        "status": "OK" if manifest is not None else "FAIL",
        "detail": {"manifest_path": str(manifest_path), "artifact_count": len(manifest.get("artifacts") or [])}
    })

    # ---- required summary/status rule (your hard rule)
    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = sum(1 for r in results if r.get("status") != "OK")
    summary = {
        "status": "PASS" if (fail == 0 and all_pass) else "FAIL",
        "actions_total": len(results),
        "actions_ok": ok,
        "actions_fail": fail,
        "upstream_all_pass": bool(all_pass),
    }

    report: Dict[str, Any] = {
        "contract_version": "finalizer/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "inputs": inputs,
        "policy": str(policy_path),
        "checks": {
            "upstream_gates": {
                "paths": {k: str(v) for k, v in gate_paths.items()},
                "gate_status": upstream_gate_status
            }
        },
        "manifest": manifest,
        "results": results,
        "summary": summary,
    }
    report["status"] = report["summary"]["status"]
    return report


def write_final_report(run_id: str, out_dir: Path, policy_path: Path) -> Dict[str, Any]:
    inputs = {
        "run_id": run_id,
        "out_dir": str(out_dir),
    }
    report = run(run_id=run_id, out_dir=out_dir, inputs=inputs, policy_path=policy_path)

    out_path = out_dir / "final_report.json"
    _write_json_no_bom(out_path, report)

    return {"out": str(out_path), "status": report.get("status")}