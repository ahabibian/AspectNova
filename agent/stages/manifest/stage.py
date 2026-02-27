from __future__ import annotations
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

def _read_json_bom_safe(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _now_utc():
    return datetime.now(timezone.utc).isoformat()

def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for ch in iter(lambda: f.read(1024 * 1024), b""):
            h.update(ch)
    return h.hexdigest()

def run(run_id: str, out_dir: Path, policy_path: Path) -> dict:
    policy = _read_json_bom_safe(policy_path) if policy_path.exists() else {"requirements": {}}
    req = policy.get("requirements") or {}

    base_out = (Path("runs") / run_id / "output").resolve()
    evi = out_dir.resolve()

    allow = [
        base_out / "scan_result.canonical.json",
        base_out / "scan_result.canonical.v1.json",

        evi / "evidence_pack.v1.json",
        evi / "evidence_pack.v1+owner.json",
        evi / "owner_enricher.stats.json",
        evi / "owner_enricher.report.json",

        evi / "verdict.json",
        evi / "command_plan.json",
        evi / "approval.json",
        evi / "execution_report.json",

        evi / "owner_enricher.gate.json",
        evi / "verdict.gate.json",
        evi / "command_plan.gate.json",
        evi / "approval.gate.json",
        evi / "execution.gate.json",
        evi / "evidence_pack.gate.json",
    ]

    artifacts = []
    for p in allow:
        if p.exists() and p.is_file():
            artifacts.append({
                "path": str(p),
                "bytes": p.stat().st_size,
                "sha256": _sha256_file(p)
            })

    min_artifacts = int(req.get("min_artifacts", 1))
    results = []

    if len(artifacts) < min_artifacts:
        results.append({"id":"MANIFEST:MIN_ARTIFACTS", "status":"FAIL",
                        "detail":{"min":min_artifacts,"got":len(artifacts)}})
    else:
        results.append({"id":"MANIFEST:MIN_ARTIFACTS", "status":"OK",
                        "detail":{"min":min_artifacts,"got":len(artifacts)}})

    out_manifest = evi / "run_manifest.json"
    manifest = {
        "run_id": run_id,
        "generated_at_utc": _now_utc(),
        "artifact_count": len(artifacts),
        "artifacts": artifacts
    }
    _write_json(out_manifest, manifest)
    results.append({"id":"MANIFEST:WROTE", "status":"OK",
                    "detail":{"out": str(out_manifest), "artifact_count": len(artifacts)}})

    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = sum(1 for r in results if r.get("status") != "OK")

    summary = {
        "status": "PASS" if fail == 0 else "FAIL",
        "actions_total": len(results),
        "actions_ok": ok,
        "actions_fail": fail,
        "artifact_count": len(artifacts)
    }

    report = {
        "contract_version": "manifest/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": _now_utc(),
        "policy": str(policy_path),
        "outputs": {"run_manifest": str(out_manifest)},
        "results": results,
        "summary": summary
    }
    report["status"] = report["summary"]["status"]
    return report
