import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def build_integrity_report(run_id: str, out_dir: Path):
    generated_at = datetime.now(timezone.utc).isoformat()

    manifest_path = out_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing run_manifest.json: {manifest_path}")

    manifest = _read_json(manifest_path)
    artifacts = manifest.get("artifacts") or []

    missing_files = 0
    hash_mismatch = 0
    checked = 0

    mismatches = []
    missing = []

    for a in artifacts:
        p = Path(a.get("path") or "")
        expected = a.get("sha256")
        if not p.exists():
            missing_files += 1
            missing.append(str(p))
            continue
        actual = _sha256_file(p)
        checked += 1
        if expected and actual.lower() != str(expected).lower():
            hash_mismatch += 1
            mismatches.append({"path": str(p), "expected": expected, "actual": actual})

    # upstream gate files (best-effort)
    gate_files = [
        out_dir / "evidence_pack.gate.json",
        out_dir / "verdict.gate.json",
        out_dir / "command_plan.gate.json",
        out_dir / "approval.gate.json",
        out_dir / "execution_report.json",  # execution gate you have is simple; keep report presence check
    ]

    missing_gate = 0
    gate_fail = 0
    gate_status = {}

    for gp in gate_files:
        if not gp.exists():
            missing_gate += 1
            gate_status[str(gp)] = "MISSING"
            continue
        # try parse and read status field
        try:
            obj = _read_json(gp)
            st = obj.get("status")
            # some are nested, some are not; normalize
            if isinstance(st, str):
                gate_status[str(gp)] = st
                if st.upper() != "PASS":
                    gate_fail += 1
            else:
                # for files without status field, just mark PRESENT
                gate_status[str(gp)] = "PRESENT"
        except Exception:
            gate_status[str(gp)] = "PRESENT_UNPARSED"

    report = {
        "contract_version": "integrity_report/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "inputs": {
            "run_manifest": str(manifest_path)
        },
        "checks": {
            "manifest": {
                "artifacts_listed": len(artifacts),
                "files_checked": checked,
                "missing_files": missing_files,
                "hash_mismatch": hash_mismatch,
                "missing_samples": missing[:25],
                "mismatch_samples": mismatches[:25]
            },
            "upstream_gates": {
                "missing": missing_gate,
                "fail": gate_fail,
                "gate_status": gate_status
            }
        },
        "summary": {
            "status": "PASS" if (missing_files == 0 and hash_mismatch == 0 and missing_gate == 0 and gate_fail == 0) else "FAIL"
        }
    }

    out_path = out_dir / "integrity_report.json"
    _write_json(out_path, report)

    return {"out": str(out_path), "status": report["summary"]["status"]}
