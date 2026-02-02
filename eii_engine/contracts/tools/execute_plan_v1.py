# DEPRECATED:
# Use execute_plan_v1_1.py (canonical executor) for pipeline.
# This file remains only for backward compatibility.


# contracts/tools/execute_plan_v1.py
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


PLAN_SCHEMA_ID = "aspectnova.command_plan"
REPORT_SCHEMA_ID = "aspectnova.execution_report"
REPORT_SCHEMA_VERSION = "aspectnova.execution_report.v1"

EXECUTOR_NAME = "executor_v1"
EXECUTOR_VERSION = "1.0.1"  # bumped (risk_level normalization)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"[execute_plan_v1] Input not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as e:
        print(f"[execute_plan_v1] Failed to read JSON: {path} ({e})", file=sys.stderr)
        raise SystemExit(2)


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v not in ("", "0", "false", "no")


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


def _savings_zero() -> Dict[str, float]:
    return {"energy_kwh_per_month": 0.0, "co2_g_per_month": 0.0, "storage_tb_per_month": 0.0}


def _savings_add(a: Dict[str, float], b: Dict[str, Any]) -> Dict[str, float]:
    return {
        "energy_kwh_per_month": float(a["energy_kwh_per_month"]) + float(b.get("energy_kwh_per_month", 0.0)),
        "co2_g_per_month": float(a["co2_g_per_month"]) + float(b.get("co2_g_per_month", 0.0)),
        "storage_tb_per_month": float(a["storage_tb_per_month"]) + float(b.get("storage_tb_per_month", 0.0)),
    }


def _policy_from_env(profile: str) -> Dict[str, Any]:
    return {
        "profile": profile,
        "allow_high_risk": _env_flag("EII_POLICY_ALLOW_HIGH", default=False),
        "require_approval_medium": _env_flag("EII_POLICY_REQUIRE_APPROVAL_MEDIUM", default=True),
    }


def _norm_risk_level(level: Any) -> str:
    """
    execution_report.v1 only allows: LOW, MEDIUM, HIGH
    Plans in the wild might contain NONE/UNKNOWN/etc.
    """
    if level is None:
        return "LOW"
    s = str(level).strip().upper()
    if s in ("", "NONE", "UNKNOWN", "UNSET", "N/A", "NA"):
        return "LOW"
    if s not in ("LOW", "MEDIUM", "HIGH"):
        return "LOW"
    return s


def _decide(policy: Dict[str, Any], cmd: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (decision, message)
    """
    ctype = cmd.get("type")
    risk = cmd.get("risk") or {}
    risk_level = _norm_risk_level(risk.get("level", "LOW"))

    if ctype == "NOOP":
        return ("SKIPPED_NOOP", "NOOP command skipped.")

    if risk_level == "HIGH" and not policy["allow_high_risk"]:
        return ("BLOCKED_POLICY", "Blocked: HIGH risk not allowed by policy.")

    if risk_level == "MEDIUM" and policy["require_approval_medium"]:
        # In v1 we don't have approval workflow; block until Step 8+ UI/approval queue
        return ("BLOCKED_POLICY", "Blocked: MEDIUM risk requires approval (not implemented in v1).")

    return ("WILL_EXECUTE", "Allowed by policy (dry-run / simulated only).")


def build_report(plan: Dict[str, Any], mode: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    idempotency = plan.get("idempotency") or {}
    plan_key = str(idempotency.get("plan_key", ""))

    trace_id = _sha256(f"{plan_key}|{mode}|{policy['profile']}")[:24]

    results: List[Dict[str, Any]] = []
    totals = _savings_zero()

    commands = plan.get("commands")
    if not isinstance(commands, list) or len(commands) == 0:
        # schema says minItems=1; but guard anyway
        commands = [{
            "command_id": "cmd-00000000",
            "type": "NOOP",
            "target": {"scope": "PROPOSAL", "ref": (plan.get("source") or {}).get("proposal_id", "unknown")},
            "rationale": "No commands present.",
            "expected_savings": _savings_zero(),
            "risk": {"level": "LOW", "notes": "synthetic"},
            "confidence": 1.0
        }]

    will_execute = blocked = skipped_noop = errors = 0

    for cmd in commands:
        if not isinstance(cmd, dict):
            errors += 1
            continue

        decision, msg = _decide(policy, cmd)

        if decision == "WILL_EXECUTE":
            will_execute += 1
            totals = _savings_add(totals, cmd.get("expected_savings") or {})
        elif decision == "BLOCKED_POLICY":
            blocked += 1
        elif decision == "SKIPPED_NOOP":
            skipped_noop += 1
        else:
            errors += 1

        risk = cmd.get("risk") or {}
        risk_level = _norm_risk_level(risk.get("level", "LOW"))

        projected = cmd.get("expected_savings") or _savings_zero()

        results.append({
            "command_id": cmd.get("command_id"),
            "type": cmd.get("type"),
            "target": cmd.get("target"),
            "decision": decision,
            "dry_run": (mode == "DRY_RUN"),
            "message": msg,
            "projected_savings": {
                "energy_kwh_per_month": float(projected.get("energy_kwh_per_month", 0.0)),
                "co2_g_per_month": float(projected.get("co2_g_per_month", 0.0)),
                "storage_tb_per_month": float(projected.get("storage_tb_per_month", 0.0)),
            },
            "risk_level": risk_level,
            "confidence": float(cmd.get("confidence", 0.0)),
        })

    key_id = _env_str("EII_KEY_ID", "local-dev")

    report = {
        "schema_id": REPORT_SCHEMA_ID,
        "schema_version": REPORT_SCHEMA_VERSION,
        "meta": {
            "generated_at": _now_iso(),
            "executor": {"name": EXECUTOR_NAME, "version": EXECUTOR_VERSION},
            "mode": mode,
            "trace_id": trace_id,
        },
        "plan": {
            "schema_id": plan.get("schema_id", ""),
            "schema_version": plan.get("schema_version", ""),
            "idempotency": {"plan_key": plan_key},
            "source": {
                "proposal_id": (plan.get("source") or {}).get("proposal_id", ""),
                "scan_id": (plan.get("source") or {}).get("scan_id", ""),
            },
        },
        "policy": policy,
        "results": results,
        "summary": {
            "total": len(results),
            "will_execute": will_execute,
            "blocked_policy": blocked,
            "skipped_noop": skipped_noop,
            "errors": errors,
            "totals": totals,
        },
        "signatures": {
            "requested": False,
            "method": "HMAC-SHA256",
            "key_id": key_id,
            "signed_at": "",
            "signature": "",
        }
    }

    return report


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print(
            "Usage: python contracts/tools/execute_plan_v1.py <command_plan_json> <out_execution_report_json> "
            "[--mode DRY_RUN|SIMULATED_EXECUTE] [--policy <name>]",
            file=sys.stderr
        )
        return 2

    in_path = Path(argv[1])
    out_path = Path(argv[2])

    mode = "DRY_RUN"
    profile = "default"

    if "--mode" in argv:
        i = argv.index("--mode")
        mode = argv[i + 1].strip().upper()
    if "--policy" in argv:
        i = argv.index("--policy")
        profile = argv[i + 1].strip()

    if mode not in ("DRY_RUN", "SIMULATED_EXECUTE"):
        print(f"[execute_plan_v1] Invalid mode: {mode}", file=sys.stderr)
        return 2

    plan = _read_json(in_path)

    # Minimal sanity checks (schema validation happens elsewhere)
    if plan.get("schema_id") != PLAN_SCHEMA_ID:
        print(
            f"[execute_plan_v1] Warning: plan.schema_id != {PLAN_SCHEMA_ID} (got {plan.get('schema_id')})",
            file=sys.stderr
        )

    policy = _policy_from_env(profile)
    report = build_report(plan, mode=mode, policy=policy)
    _write_json(out_path, report)

    print(f"[execute_plan_v1] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
