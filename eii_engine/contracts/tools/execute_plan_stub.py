# contracts/tools/execute_plan_stub.py
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"[execute_plan_stub] Input not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as e:
        print(f"[execute_plan_stub] Failed to read JSON: {path} ({e})", file=sys.stderr)
        raise SystemExit(2)


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_nonempty_str(v: Any, min_len: int = 1) -> bool:
    return isinstance(v, str) and len(v.strip()) >= min_len


def validate_minimal(plan: Dict[str, Any]) -> List[str]:
    issues: List[str] = []

    # Root keys expected by command_plan schema
    if "schema_id" not in plan:
        issues.append("Missing root key: 'schema_id'")
    if "schema_version" not in plan:
        issues.append("Missing root key: 'schema_version'")
    if "idempotency" not in plan:
        issues.append("Missing root key: 'idempotency'")
    if "commands" not in plan:
        issues.append("Missing root key: 'commands'")
    if "signatures" not in plan:
        issues.append("Missing root key: 'signatures'")

    # idempotency must be object with plan_key
    idem = plan.get("idempotency")
    if not isinstance(idem, dict):
        issues.append("idempotency must be an object.")
    else:
        if not _is_nonempty_str(idem.get("plan_key"), 8):
            issues.append("idempotency.plan_key must be a non-empty string (len>=8).")

    # commands must be non-empty list
    cmds = plan.get("commands")
    if not isinstance(cmds, list) or len(cmds) == 0:
        issues.append("commands must be a non-empty array.")
    else:
        for i, c in enumerate(cmds[:50]):  # cap
            if not isinstance(c, dict):
                issues.append(f"commands[{i}] must be an object.")
                continue
            if not _is_nonempty_str(c.get("command_id"), 8):
                issues.append(f"commands[{i}].command_id too short/empty.")
            if not _is_nonempty_str(c.get("type"), 2):
                issues.append(f"commands[{i}].type missing.")
            tgt = c.get("target")
            if not isinstance(tgt, dict):
                issues.append(f"commands[{i}].target must be an object.")
            else:
                if tgt.get("scope") not in ("FILE", "PROPOSAL"):
                    issues.append(f"commands[{i}].target.scope must be FILE or PROPOSAL.")
                if not _is_nonempty_str(tgt.get("ref"), 3):
                    issues.append(f"commands[{i}].target.ref missing/too short.")
            if "rationale" not in c:
                issues.append(f"commands[{i}].rationale required.")
            if "expected_savings" not in c:
                issues.append(f"commands[{i}].expected_savings required.")
            if "risk" not in c:
                issues.append(f"commands[{i}].risk required.")
            if "confidence" not in c:
                issues.append(f"commands[{i}].confidence required.")

    # signatures.key_id must be set (not empty/unset)
    sig = plan.get("signatures")
    if not isinstance(sig, dict):
        issues.append("signatures must be an object.")
    else:
        key_id = sig.get("key_id")
        if not _is_nonempty_str(key_id, 3) or str(key_id).strip().lower() in ("unset", "none", "null"):
            issues.append("signatures.key_id must be set (not empty/unset).")

    return issues


def execute_stub(plan: Dict[str, Any]) -> Dict[str, Any]:
    # Dry-run: هیچ چیزی واقعاً اجرا نمی‌شود، فقط گزارش می‌سازیم.
    cmds = plan.get("commands") if isinstance(plan.get("commands"), list) else []
    items = []
    for c in cmds:
        if not isinstance(c, dict):
            continue
        items.append(
            {
                "command_id": c.get("command_id"),
                "type": c.get("type"),
                "target": c.get("target"),
                "status": "DRY_RUN_OK",
                "detail": "No real execution performed (stub).",
            }
        )

    return {
        "schema_id": "aspectnova.execution_report",
        "schema_version": "aspectnova.execution_report.v1",
        "generated_at": _now_iso(),
        "plan": {
            "schema_id": plan.get("schema_id"),
            "schema_version": plan.get("schema_version"),
            "idempotency": plan.get("idempotency"),
        },
        "results": items,
        "summary": {
            "total": len(items),
            "dry_run": True,
        },
    }


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print("Usage: python contracts/tools/execute_plan_stub.py <command_plan_json> <out_report_json> [--strict]", file=sys.stderr)
        return 2

    in_path = Path(argv[1])
    out_path = Path(argv[2])
    strict = "--strict" in argv[3:]

    plan = _read_json(in_path)
    issues = validate_minimal(plan)

    if issues:
        print("[execute_plan_stub] Validation issues:")
        for it in issues:
            print(f" - {it}")
        if strict:
            return 2

    report = execute_stub(plan)
    _write_json(out_path, report)
    print(f"[execute_plan_stub] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
