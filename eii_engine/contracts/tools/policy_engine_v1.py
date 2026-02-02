# contracts/tools/policy_engine_v1.py
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


PLAN_SCHEMA_ID = "aspectnova.command_plan"
DECISION_SCHEMA_ID = "aspectnova.policy_decision"
DECISION_SCHEMA_VERSION = "aspectnova.policy_decision.v1"

ENGINE_NAME = "policy_engine_v1"
ENGINE_VERSION = "1.0.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"[policy_engine_v1] Input not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as e:
        print(f"[policy_engine_v1] Failed to read JSON: {path} ({e})", file=sys.stderr)
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
    # Same semantics as executor_v1, but here we output a decision object.
    return {
        "profile": profile,
        "allow_high_risk": _env_flag("EII_POLICY_ALLOW_HIGH", default=False),
        "require_approval_medium": _env_flag("EII_POLICY_REQUIRE_APPROVAL_MEDIUM", default=True),
    }


def _decide(policy: Dict[str, Any], cmd: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (decision, reason)
    Decisions:
      - SKIP_NOOP
      - BLOCK_HIGH_RISK
      - REQUIRE_APPROVAL_MEDIUM
      - ALLOW
    """
    ctype = cmd.get("type", "")
    risk = cmd.get("risk") or {}
    risk_level = str(risk.get("level", "LOW")).upper()

    if ctype == "NOOP":
        return ("SKIP_NOOP", "NOOP command skipped.")

    if risk_level == "HIGH" and not policy["allow_high_risk"]:
        return ("BLOCK_HIGH_RISK", "Blocked: HIGH risk not allowed by policy.")

    if risk_level == "MEDIUM" and policy["require_approval_medium"]:
        # Approval workflow comes later; for v1 we mark it as requiring approval.
        return ("REQUIRE_APPROVAL_MEDIUM", "Requires approval: MEDIUM risk under current policy.")

    return ("ALLOW", "Allowed by policy.")


def _strict_validate_plan_minimal(plan: Dict[str, Any]) -> None:
    # We rely on validate_schema.py for full JSON-schema validation.
    # Here we just fail fast if it's clearly not a plan.
    if not isinstance(plan, dict):
        raise SystemExit("[policy_engine_v1] Plan must be a JSON object.")
    if plan.get("schema_id") != PLAN_SCHEMA_ID:
        raise SystemExit(f"[policy_engine_v1] plan.schema_id must be '{PLAN_SCHEMA_ID}' (got {plan.get('schema_id')!r})")
    if "schema_version" not in plan:
        raise SystemExit("[policy_engine_v1] plan.schema_version missing.")
    if not isinstance(plan.get("commands"), list) or len(plan["commands"]) < 1:
        raise SystemExit("[policy_engine_v1] plan.commands must be a non-empty list.")
    # risk normalizer should ensure these are strings/enums etc, but we don't enforce here beyond basic types.


def build_policy_decision(plan: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    idempotency = plan.get("idempotency") or {}
    plan_key = str(idempotency.get("plan_key", ""))

    trace_id = _sha256(f"{plan_key}|{policy['profile']}|{ENGINE_NAME}")[:24]

    decisions: List[Dict[str, Any]] = []
    totals_allowed = _savings_zero()

    allow = block = require_approval = skip_noop = errors = 0

    for cmd in plan.get("commands", []):
        if not isinstance(cmd, dict):
            errors += 1
            continue

        decision, reason = _decide(policy, cmd)

        risk = cmd.get("risk") or {}
        risk_level = str(risk.get("level", "LOW")).upper()

        projected = cmd.get("expected_savings") or _savings_zero()
        projected_norm = {
            "energy_kwh_per_month": float(projected.get("energy_kwh_per_month", 0.0)),
            "co2_g_per_month": float(projected.get("co2_g_per_month", 0.0)),
            "storage_tb_per_month": float(projected.get("storage_tb_per_month", 0.0)),
        }

        if decision == "ALLOW":
            allow += 1
            totals_allowed = _savings_add(totals_allowed, projected_norm)
        elif decision == "BLOCK_HIGH_RISK":
            block += 1
        elif decision == "REQUIRE_APPROVAL_MEDIUM":
            require_approval += 1
        elif decision == "SKIP_NOOP":
            skip_noop += 1
        else:
            errors += 1

        decisions.append(
            {
                "command_id": cmd.get("command_id", ""),
                "type": cmd.get("type", ""),
                "target": cmd.get("target", {}),
                "risk_level": risk_level,
                "decision": decision,
                "reason": reason,
                "confidence": float(cmd.get("confidence", 0.0)),
                "projected_savings": projected_norm,
            }
        )

    key_id = _env_str("EII_KEY_ID", "local-dev")

    out = {
        "schema_id": DECISION_SCHEMA_ID,
        "schema_version": DECISION_SCHEMA_VERSION,
        "meta": {
            "generated_at": _now_iso(),
            "engine": {"name": ENGINE_NAME, "version": ENGINE_VERSION},
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
        "decisions": decisions,
        "summary": {
            "total": len(decisions),
            "allow": allow,
            "blocked": block,
            "require_approval": require_approval,
            "skipped_noop": skip_noop,
            "errors": errors,
            "totals_allowed": totals_allowed,
        },
        "signatures": {
            "requested": False,
            "method": "HMAC-SHA256",
            "key_id": key_id,
            "signed_at": "",
            "signature": "",
        },
    }

    return out


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print(
            "Usage: python contracts/tools/policy_engine_v1.py <command_plan_norm_json> <out_policy_decision_json> "
            "[--policy <name>] [--strict]",
            file=sys.stderr,
        )
        return 2

    in_path = Path(argv[1])
    out_path = Path(argv[2])

    profile = "default"
    strict = False

    if "--policy" in argv:
        i = argv.index("--policy")
        profile = argv[i + 1].strip()

    if "--strict" in argv:
        strict = True

    plan = _read_json(in_path)

    if strict:
        _strict_validate_plan_minimal(plan)

    policy = _policy_from_env(profile)
    decision = build_policy_decision(plan, policy=policy)
    _write_json(out_path, decision)

    print(f"[policy_engine_v1] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
