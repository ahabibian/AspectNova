from __future__ import annotations

import json
import sys
from pathlib import Path


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python tools/gate_preflight.py <preflight.report.json> <policy.json>")
        return 2

    rep = Path(sys.argv[1])
    pol = Path(sys.argv[2])

    if not rep.exists():
        print(json.dumps({"stage": "preflight", "status": "FAIL", "reasons": [{"type": "missing_report"}]}, indent=2))
        return 1

    report = _read_json(rep)
    policy = _read_json(pol)

    req = (policy.get("requirements") or {})
    allow_warnings = bool(req.get("allow_warnings", True))
    max_aliases = int(req.get("max_aliases_created", 999999))

    errors = report.get("errors") or []
    warnings = report.get("warnings") or []
    aliases_created = int((report.get("metrics") or {}).get("aliases_created") or 0)

    reasons = []
    if errors:
        reasons.append({"type": "preflight_errors", "detail": {"count": len(errors)}})
    if (not allow_warnings) and warnings:
        reasons.append({"type": "preflight_warnings_blocking", "detail": {"count": len(warnings)}})
    if aliases_created > max_aliases:
        reasons.append({"type": "too_many_aliases_created", "detail": {"max": max_aliases, "got": aliases_created}})

    status = "PASS" if not reasons else "FAIL"
    out = {
        "stage": "preflight",
        "policy_version": policy.get("policy_version", "unknown"),
        "status": status,
        "reasons": reasons,
        "summary": {
            "fixes": len(report.get("fixes") or []),
            "warnings": len(warnings),
            "errors": len(errors),
            "aliases_created": aliases_created
        }
    }
    print(json.dumps(out, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())