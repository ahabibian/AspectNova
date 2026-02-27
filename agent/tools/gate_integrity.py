import json
import sys
from pathlib import Path

def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def fail(obj, code=1):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)

def main():
    if len(sys.argv) < 3:
        fail({"error":"usage","example":"python gate_integrity.py <report> <policy>"}, 2)

    report_path = Path(sys.argv[1])
    policy_path = Path(sys.argv[2])

    report = read_json(report_path)
    policy = read_json(policy_path)

    req = policy.get("requirements") or {}

    checks = report.get("checks") or {}
    man = checks.get("manifest") or {}
    gates = checks.get("upstream_gates") or {}

    missing_files = int(man.get("missing_files") or 0)
    hash_mismatch = int(man.get("hash_mismatch") or 0)
    missing_gate = int(gates.get("missing") or 0)
    gate_fail = int(gates.get("fail") or 0)

    reasons = []

    if missing_files > int(req.get("max_missing_files", 0)):
        reasons.append("missing_files")

    if hash_mismatch > int(req.get("max_hash_mismatch", 0)):
        reasons.append("hash_mismatch")

    if missing_gate > int(req.get("max_missing_gate_files", 0)):
        reasons.append("missing_gate_files")

    if gate_fail > int(req.get("max_gate_fail", 0)):
        reasons.append("gate_fail")

    status = "PASS" if not reasons else "FAIL"

    out = {
        "stage": "integrity",
        "status": status,
        "reasons": reasons,
        "counts": {
            "missing_files": missing_files,
            "hash_mismatch": hash_mismatch,
            "missing_gate_files": missing_gate,
            "gate_fail": gate_fail
        }
    }

    if status == "PASS":
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    fail(out, 1)

if __name__ == "__main__":
    main()
