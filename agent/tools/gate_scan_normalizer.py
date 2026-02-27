from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python tools/gate_scan_normalizer.py <scan_v1.json> <policy.json>")
        return 2

    scan_path = Path(sys.argv[1])
    pol_path = Path(sys.argv[2])

    if not scan_path.exists():
        print(json.dumps({
            "stage": "scan_normalizer",
            "status": "FAIL",
            "reasons": [{"type": "missing_scan_v1", "detail": {"path": str(scan_path)}}],
            "inputs": {"scan_v1": str(scan_path), "policy": str(pol_path)}
        }, indent=2))
        return 1

    policy = json.loads(pol_path.read_text(encoding="utf-8-sig"))
    scan = json.loads(scan_path.read_text(encoding="utf-8-sig"))

    expected_schema_id = policy.get("requirements", {}).get("schema_id")
    got_schema_id = scan.get("schema_id")

    reasons = []
    if expected_schema_id and got_schema_id != expected_schema_id:
        reasons.append({"type": "schema_id_mismatch", "detail": {"expected": expected_schema_id, "got": got_schema_id}})

    status = "PASS" if not reasons else "FAIL"
    out = {
        "stage": "scan_normalizer",
        "policy_version": policy.get("policy_version", "unknown"),
        "status": status,
        "reasons": reasons,
        "inputs": {"scan_v1": str(scan_path).replace("/", "\\"), "policy": str(pol_path).replace("/", "\\")},
        "summary": {"schema_id": got_schema_id, "items": (scan.get("counts") or {}).get("items_out")}
    }
    print(json.dumps(out, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

