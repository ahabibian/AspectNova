from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional


# -------------------------
# Utilities
# -------------------------

def utc_now_iso() -> str:
    # timezone-aware
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def norm_rel(path_str: str) -> str:
    return str(path_str).replace("\\", "/").lstrip("./")


def safe_join(root: Path, rel: str) -> Path:
    rel = norm_rel(rel)
    out = (root / rel).resolve()
    root_r = root.resolve()
    if not str(out).startswith(str(root_r)):
        raise ValueError(f"Unsafe path traversal: {rel}")
    return out


def get_plan_key(plan: Dict[str, Any]) -> str:
    # Accept multiple historical layouts:
    # 1) plan["idempotency"]["plan_key"]
    # 2) plan["idempotency"]["key"]
    # 3) plan["plan_key"]
    idem = plan.get("idempotency") or {}
    pk = (
        idem.get("plan_key")
        or idem.get("key")
        or plan.get("plan_key")
        or (plan.get("idempotency") or {}).get("planKey")
    )
    if not pk or not isinstance(pk, str):
        raise ValueError("command plan missing idempotency.plan_key (or idempotency.key).")
    return pk


def archive_dir_to(dest_dir: Path, src_dir: Path) -> None:
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    if dest_dir.exists():
        # idempotency: if already archived, remove and re-create cleanly
        shutil.rmtree(dest_dir)
    shutil.move(str(src_dir), str(dest_dir))


def make_zip(zip_path: Path, folder: Path) -> None:
    """
    Creates zip at zip_path (without double .zip) from folder contents.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    # shutil.make_archive wants base_name without extension
    base_name = zip_path
    if zip_path.name.lower().endswith(".zip"):
        base_name = zip_path.with_suffix("")  # remove .zip

    # If exists, overwrite
    if zip_path.exists():
        zip_path.unlink()

    shutil.make_archive(str(base_name), "zip", root_dir=str(folder))


# -------------------------
# Executor
# -------------------------

def execute_archive(
    repo_root: Path,
    cmd: Dict[str, Any],
    plan_key: str,
) -> Dict[str, Any]:
    target = cmd.get("target") or {}
    if target.get("scope") != "DIRECTORY":
        raise ValueError("ARCHIVE only supports target.scope=DIRECTORY")

    ref = target.get("ref")
    if not ref or not isinstance(ref, str):
        raise ValueError("ARCHIVE target.ref is missing")

    # For safety, we only allow relative refs (like "output" or "agent/output")
    rel = norm_rel(ref)
    src_dir = safe_join(repo_root, rel)

    if not src_dir.exists():
        # Treat as no-op but record message
        return {
            "message": f"SKIPPED: missing directory: {src_dir}",
            "archived_from": str(src_dir),
            "archived_to": None,
            "zip_path": None,
            "skipped": True,
        }

    # Archive destination: <src_parent>/.aspectnova_archive/<plan_key_prefix>/output
    # Example: agent/output -> agent/.aspectnova_archive/<plan_key_prefix>/output
    src_parent = src_dir.parent
    archive_root = src_parent / ".aspectnova_archive" / plan_key[:12]
    dest_dir = archive_root / src_dir.name

    archive_dir_to(dest_dir=dest_dir, src_dir=src_dir)

    # Create zip next to folder: output.zip
    zip_path = archive_root / f"{src_dir.name}.zip"
    make_zip(zip_path=zip_path, folder=dest_dir)

    return {
        "message": f"ARCHIVED: {src_dir} -> {dest_dir} (ZIP: {zip_path})",
        "archived_from": str(src_dir),
        "archived_to": str(dest_dir),
        "zip_path": str(zip_path),
        "skipped": False,
    }


def build_report(
    plan: Dict[str, Any],
    policy: Dict[str, Any],
    results: List[Dict[str, Any]],
    mode: str,
) -> Dict[str, Any]:
    totals = {
        "energy_kwh_per_month": 0.0,
        "co2_g_per_month": 0.0,
        "storage_tb_per_month": 0.0,
    }

    will_execute = sum(1 for r in results if r.get("decision") == "WILL_EXECUTE")
    blocked = sum(1 for r in results if r.get("decision") == "BLOCKED_POLICY")
    skipped = sum(1 for r in results if r.get("decision") == "SKIPPED_NOOP")
    errors = sum(1 for r in results if r.get("decision") == "ERROR")

    return {
        "schema_id": "aspectnova.execution_report",
        "schema_version": "aspectnova.execution_report.v1",
        "meta": {
            "generated_at": utc_now_iso(),
            "runner": {"id": "execute_plan_v1_1", "mode": mode},
        },
        "plan": {
            "schema_id": plan.get("schema_id", "aspectnova.command_plan"),
            "schema_version": plan.get("schema_version", "v1"),
            "plan_key": get_plan_key(plan),
        },
        "policy": {
            "profile": (policy.get("profile") if isinstance(policy, dict) else "default") or "default",
            "decision": (policy.get("decision") if isinstance(policy, dict) else "") or "",
            "message": (policy.get("message") if isinstance(policy, dict) else "") or "",
        },
        "results": results,
        "summary": {
            "total": len(results),
            "will_execute": will_execute,
            "blocked_policy": blocked,
            "skipped_noop": skipped,
            "errors": errors,
            "totals": totals,
        },
        "signatures": [],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command_plan_json")
    ap.add_argument("policy_decision_json")
    ap.add_argument("execution_report_out_json")
    ap.add_argument("--mode", choices=["DRY_RUN", "REAL_EXECUTE"], default="DRY_RUN")
    ap.add_argument("--approval-token-json", required=False)
    ap.add_argument("--scan-payload-json", required=False)
    args = ap.parse_args()

    plan = read_json(args.command_plan_json)
    policy = read_json(args.policy_decision_json) if Path(args.policy_decision_json).exists() else {"profile": "default"}

    plan_key = get_plan_key(plan)

    # Determine repo root as current working directory (matches your usage)
    repo_root = Path(os.getcwd()).resolve()

    results: List[Dict[str, Any]] = []
    commands = plan.get("commands") or []
    if not isinstance(commands, list):
        raise SystemExit("Invalid command plan: commands must be a list")

    for i, cmd in enumerate(commands):
        cmd_type = (cmd.get("type") or "").upper()
        cmd_id = cmd.get("command_id") or cmd.get("id") or f"cmd-{i:03d}"

        if cmd_type == "NOOP":
            results.append({
                "command_id": cmd_id,
                "type": "NOOP",
                "target": cmd.get("target"),
                "decision": "SKIPPED_NOOP",
                "dry_run": (args.mode != "REAL_EXECUTE"),
                "message": "NOOP",
                "projected_savings": {
                    "energy_kwh_per_month": 0.0,
                    "co2_g_per_month": 0.0,
                    "storage_tb_per_month": 0.0,
                },
                "risk_level": cmd.get("risk_level", "LOW"),
                "confidence": cmd.get("confidence", 0.7),
            })
            continue

        if cmd_type == "ARCHIVE":
            try:
                if args.mode != "REAL_EXECUTE":
                    results.append({
                        "command_id": cmd_id,
                        "type": "ARCHIVE",
                        "target": cmd.get("target"),
                        "decision": "WILL_EXECUTE",
                        "dry_run": True,
                        "message": "DRY_RUN: would archive and zip target directory",
                        "projected_savings": {
                            "energy_kwh_per_month": 0.0,
                            "co2_g_per_month": 0.0,
                            "storage_tb_per_month": 0.0,
                        },
                        "risk_level": cmd.get("risk_level", "MEDIUM"),
                        "confidence": cmd.get("confidence", 0.7),
                    })
                else:
                    info = execute_archive(repo_root=repo_root, cmd=cmd, plan_key=plan_key)
                    decision = "SKIPPED_NOOP" if info.get("skipped") else "WILL_EXECUTE"
                    results.append({
                        "command_id": cmd_id,
                        "type": "ARCHIVE",
                        "target": cmd.get("target"),
                        "decision": decision,
                        "dry_run": False,
                        "message": info.get("message", ""),
                        "projected_savings": {
                            "energy_kwh_per_month": 0.0,
                            "co2_g_per_month": 0.0,
                            "storage_tb_per_month": 0.0,
                        },
                        "risk_level": cmd.get("risk_level", "MEDIUM"),
                        "confidence": cmd.get("confidence", 0.7),
                        "artifacts": {
                            "archived_to": info.get("archived_to"),
                            "zip_path": info.get("zip_path"),
                        },
                    })
            except Exception as e:
                results.append({
                    "command_id": cmd_id,
                    "type": "ARCHIVE",
                    "target": cmd.get("target"),
                    "decision": "ERROR",
                    "dry_run": (args.mode != "REAL_EXECUTE"),
                    "message": f"ERROR: {e}",
                    "projected_savings": {
                        "energy_kwh_per_month": 0.0,
                        "co2_g_per_month": 0.0,
                        "storage_tb_per_month": 0.0,
                    },
                    "risk_level": "HIGH",
                    "confidence": 0.3,
                })
            continue

        # Unknown command types
        results.append({
            "command_id": cmd_id,
            "type": cmd_type or "UNKNOWN",
            "target": cmd.get("target"),
            "decision": "SKIPPED_NOOP",
            "dry_run": (args.mode != "REAL_EXECUTE"),
            "message": f"SKIPPED: unsupported command type: {cmd_type}",
            "projected_savings": {
                "energy_kwh_per_month": 0.0,
                "co2_g_per_month": 0.0,
                "storage_tb_per_month": 0.0,
            },
            "risk_level": "LOW",
            "confidence": 0.5,
        })

    report = build_report(plan=plan, policy=policy, results=results, mode=args.mode)
    write_json(args.execution_report_out_json, report)
    print(f"[execute_plan_v1_1] OK -> wrote: {args.execution_report_out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
