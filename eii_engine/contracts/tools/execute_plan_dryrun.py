from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List


EXECUTOR_NAME = "execute_plan_dryrun"
EXECUTOR_VERSION = "exec.dryrun.v1"


# ============================================================
# Time helpers
# ============================================================

def utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ============================================================
# IO helpers
# ============================================================

def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ============================================================
# Normalization helpers
# ============================================================

def to_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        return v if v >= 0 else default
    except Exception:
        return default


def pick(mapping: Dict[str, Any], *keys: str, default=None):
    for key in keys:
        if isinstance(mapping, dict) and key in mapping:
            return mapping[key]
    return default


def ensure_min_length(value: Any, prefix: str, min_len: int = 8) -> str:
    text = str(value).strip() if value is not None else ""
    if len(text) >= min_len:
        return text

    base = (prefix + text).replace(" ", "_")
    if len(base) < min_len:
        base = (base + "00000000")[:min_len]

    return base


def make_trace_id(plan_key: str) -> str:
    key = ensure_min_length(plan_key, "plan_", 8)
    return f"rep_{key}"[:64]


# ============================================================
# Environment flags (explicit, testable)
# ============================================================

def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


# ============================================================
# Command mapping
# ============================================================

def normalize_command_type(value: Any) -> str:
    allowed = {"DELETE", "ARCHIVE", "MOVE", "COMPRESS", "NOOP", "REVIEW"}
    t = str(value).strip().upper() if value is not None else "NOOP"
    return t if t in allowed else "NOOP"


def normalize_risk_level(value: Any) -> str:
    v = str(value).strip().upper() if value is not None else "LOW"
    if v in {"LOW", "MEDIUM", "HIGH"}:
        return v
    if "HIGH" in v:
        return "HIGH"
    if "MED" in v:
        return "MEDIUM"
    return "LOW"


# ============================================================
# Savings handling
# ============================================================

def build_projected_savings(command: Dict[str, Any]) -> Dict[str, float]:
    base = {}

    if isinstance(command.get("projected_savings"), dict):
        base = command["projected_savings"]
    elif isinstance(command.get("expected_savings"), dict):
        base = command["expected_savings"]

    storage_tb = 0.0
    raw_bytes = pick(command, "bytes", "size_bytes", default=0)
    try:
        storage_tb = max(0.0, float(raw_bytes) / (1024 ** 4))
    except Exception:
        storage_tb = 0.0

    return {
        "energy_kwh_per_month": max(0.0, to_float(base.get("energy_kwh_per_month"), 0.0)),
        "co2_g_per_month": max(0.0, to_float(base.get("co2_g_per_month"), 0.0)),
        "storage_tb_per_month": max(
            0.0, to_float(base.get("storage_tb_per_month"), storage_tb)
        ),
    }


def sum_savings(results: List[Dict[str, Any]]) -> Dict[str, float]:
    energy = co2 = storage = 0.0

    for r in results:
        ps = r.get("projected_savings", {})
        energy += to_float(ps.get("energy_kwh_per_month"), 0.0)
        co2 += to_float(ps.get("co2_g_per_month"), 0.0)
        storage += to_float(ps.get("storage_tb_per_month"), 0.0)

    return {
        "energy_kwh_per_month": max(0.0, energy),
        "co2_g_per_month": max(0.0, co2),
        "storage_tb_per_month": max(0.0, storage),
    }


# ============================================================
# Main
# ============================================================

def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python execute_plan_dryrun.py <command_plan.json> <out_report.json>")
        return 2

    plan_path = sys.argv[1]
    out_path = sys.argv[2]

    if not os.path.exists(plan_path):
        print(f"[execute_dryrun] Input not found: {plan_path}")
        return 2

    plan = read_json(plan_path)

    meta = plan.get("meta", {}) if isinstance(plan.get("meta"), dict) else {}
    source = plan.get("source", {}) if isinstance(plan.get("source"), dict) else {}
    idem = plan.get("idempotency", {}) if isinstance(plan.get("idempotency"), dict) else {}

    proposal_id = ensure_min_length(pick(source, "proposal_id", default="proposal"), "proposal_")
    scan_id = ensure_min_length(pick(source, "scan_id", default="scan"), "scan_")
    plan_key = ensure_min_length(pick(idem, "plan_key", default="plan"), "plan_")

    execute_requested = env_flag("ASPECTNOVA_EXECUTE_REQUESTED", False)
    confirm_received = env_flag("ASPECTNOVA_CONFIRM_RECEIVED", False)

    allow_high_risk = env_flag("ASPECTNOVA_ALLOW_HIGH_RISK", False)
    require_approval_medium = env_flag("ASPECTNOVA_REQUIRE_APPROVAL_MEDIUM", True)

    commands = plan.get("commands", [])
    if not isinstance(commands, list) or not commands:
        commands = [{
            "command_id": "cmd_00000000",
            "type": "NOOP",
            "target": {"scope": "PROPOSAL", "ref": proposal_id}
        }]

    results: List[Dict[str, Any]] = []

    for idx, cmd in enumerate(commands):
        command_id = ensure_min_length(
            pick(cmd, "command_id", default=f"cmd_{idx:08d}"),
            "cmd_"
        )

        cmd_type = normalize_command_type(cmd.get("type"))
        risk_level = normalize_risk_level(
            pick(cmd.get("risk", {}), "level", default=cmd.get("risk_level", "LOW"))
        )

        target = cmd.get("target", {}) if isinstance(cmd.get("target"), dict) else {}
        scope = str(pick(target, "scope", default="PROPOSAL")).upper()
        if scope not in {"FILE", "PROPOSAL"}:
            scope = "PROPOSAL"

        ref = ensure_min_length(
            pick(target, "ref", default=proposal_id),
            "ref_"
        )

        if cmd_type == "NOOP":
            decision = "SKIPPED_NOOP"
            message = "noop"
            confidence = 1.0
        else:
            decision = "BLOCKED_POLICY"
            message = "dry-run: execution disabled"
            confidence = to_float(cmd.get("confidence"), 0.5)

            if execute_requested and confirm_received:
                decision = "WILL_EXECUTE"
                message = "dry-run: execution authorized"

            if risk_level == "HIGH" and not allow_high_risk:
                decision = "BLOCKED_POLICY"
                message = "policy: high risk not allowed"

            if risk_level == "MEDIUM" and require_approval_medium:
                decision = "BLOCKED_POLICY"
                message = "policy: approval required"

        results.append({
            "command_id": command_id,
            "type": cmd_type,
            "target": {"scope": scope, "ref": ref},
            "decision": decision,
            "dry_run": True,
            "message": message,
            "projected_savings": build_projected_savings(cmd),
            "risk_level": risk_level,
            "confidence": max(0.0, min(1.0, confidence)),
        })

    totals = sum_savings(results)

    report = {
        "schema_id": "aspectnova.execution_report",
        "schema_version": "aspectnova.execution_report.v1",
        "meta": {
            "generated_at": utc_now_z(),
            "executor": {
                "name": EXECUTOR_NAME,
                "version": EXECUTOR_VERSION,
            },
            "mode": "DRY_RUN",
            "trace_id": make_trace_id(plan_key),
        },
        "plan": {
            "schema_id": "aspectnova.command_plan",
            "schema_version": "aspectnova.command_plan.v1",
            "idempotency": {"plan_key": plan_key},
            "source": {
                "proposal_id": proposal_id,
                "scan_id": scan_id,
            },
        },
        "policy": {
            "profile": "default",
            "allow_high_risk": allow_high_risk,
            "require_approval_medium": require_approval_medium,
        },
        "results": results,
        "summary": {
            "total": len(results),
            "will_execute": sum(1 for r in results if r["decision"] == "WILL_EXECUTE"),
            "blocked_policy": sum(1 for r in results if r["decision"] == "BLOCKED_POLICY"),
            "skipped_noop": sum(1 for r in results if r["decision"] == "SKIPPED_NOOP"),
            "errors": 0,
            "totals": totals,
        },
        "signatures": {
            "requested": False,
            "method": "HMAC-SHA256",
            "key_id": "unset",
            "signed_at": "",
            "signature": "",
        },
    }

    write_json(out_path, report)
    print(f"[execute_dryrun] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
