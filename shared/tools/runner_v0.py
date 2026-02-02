from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# -------------------------
# Errors
# -------------------------
class RunnerError(Exception):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RunnerError(f"Input not found: {path}")
    try:
        txt = path.read_text(encoding="utf-8")
        return json.loads(txt)
    except json.JSONDecodeError as e:
        raise RunnerError(f"Invalid JSON in {path}: {e}") from e
    except Exception as e:
        raise RunnerError(f"Failed reading {path}: {e}") from e


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _validate_execution_plan(doc: Dict[str, Any]) -> None:
    if doc.get("schema_id") != "execution-plan":
        raise RunnerError("execution_plan.schema_id must be 'execution-plan'")
    ver = doc.get("schema_version")
    if not _is_nonempty_str(ver):
        raise RunnerError("execution_plan.schema_version is required")
    # We accept v1.1 and later v1.x in this runner
    if not str(ver).startswith("v1."):
        raise RunnerError("execution_plan.schema_version must start with 'v1.' (expected v1.1)")

    if not isinstance(doc.get("decision_snapshot"), dict):
        raise RunnerError("execution_plan.decision_snapshot must be an object")
    if not _is_nonempty_str(doc["decision_snapshot"].get("policy_id")):
        raise RunnerError("execution_plan.decision_snapshot.policy_id is required")

    if not isinstance(doc.get("payload_snapshot"), dict):
        raise RunnerError("execution_plan.payload_snapshot must be an object")
    if not _is_nonempty_str(doc["payload_snapshot"].get("schema_id")):
        raise RunnerError("execution_plan.payload_snapshot.schema_id is required")
    if not _is_nonempty_str(doc["payload_snapshot"].get("schema_version")):
        raise RunnerError("execution_plan.payload_snapshot.schema_version is required")

    plan = doc.get("plan")
    if not isinstance(plan, list) or len(plan) == 0:
        raise RunnerError("execution_plan.plan must be a non-empty list")

    for i, a in enumerate(plan):
        if not isinstance(a, dict):
            raise RunnerError(f"execution_plan.plan[{i}] must be an object")
        if not _is_nonempty_str(a.get("id")):
            raise RunnerError(f"execution_plan.plan[{i}].id is required")
        if not _is_nonempty_str(a.get("type")):
            raise RunnerError(f"execution_plan.plan[{i}].type is required")
        if not _is_nonempty_str(a.get("title")):
            raise RunnerError(f"execution_plan.plan[{i}].title is required")


@dataclass
class ActionResult:
    id: str
    type: str
    title: str
    status: str  # ok | skipped | blocked | failed
    message: str
    started_at: str
    finished_at: str
    details: Dict[str, Any]


def _run_action(action: Dict[str, Any], *, execute: bool, confirm: bool) -> ActionResult:
    started = _utc_now_iso()

    aid = str(action.get("id"))
    atype = str(action.get("type"))
    title = str(action.get("title"))

    # Safety defaults
    dry_run_flag = bool(action.get("dry_run", True))

    try:
        if atype == "analysis":
            # v0: simulate analysis by echoing key inputs
            details = {
                "dry_run": True,
                "inputs": action.get("inputs", {}),
                "note": "Runner v0 does not compute anything heavy; it only validates and summarizes.",
            }
            finished = _utc_now_iso()
            return ActionResult(
                id=aid,
                type=atype,
                title=title,
                status="ok",
                message="analysis simulated",
                started_at=started,
                finished_at=finished,
                details=details,
            )

        if atype == "execution":
            guard = action.get("guardrails") if isinstance(action.get("guardrails"), dict) else {}
            require_user_confirm = bool(guard.get("require_user_confirm", True))

            if not execute:
                finished = _utc_now_iso()
                return ActionResult(
                    id=aid,
                    type=atype,
                    title=title,
                    status="skipped",
                    message="execution skipped (run with --execute to allow execution phase)",
                    started_at=started,
                    finished_at=finished,
                    details={
                        "dry_run": True,
                        "guardrails": guard,
                        "require_user_confirm": require_user_confirm,
                    },
                )

            if require_user_confirm and not confirm:
                finished = _utc_now_iso()
                return ActionResult(
                    id=aid,
                    type=atype,
                    title=title,
                    status="blocked",
                    message="blocked: require_user_confirm is true (run with --confirm to proceed)",
                    started_at=started,
                    finished_at=finished,
                    details={
                        "dry_run": True,
                        "guardrails": guard,
                        "require_user_confirm": True,
                    },
                )

            # Even with --execute + --confirm, v0 remains SAFE:
            # No real delete/cleanup is performed. We only simulate.
            finished = _utc_now_iso()
            return ActionResult(
                id=aid,
                type=atype,
                title=title,
                status="ok",
                message="execution simulated (SAFE MODE: no real changes performed in v0)",
                started_at=started,
                finished_at=finished,
                details={
                    "dry_run": True if dry_run_flag else True,  # force true in v0
                    "guardrails": guard,
                    "note": "Runner v0 never performs destructive operations.",
                },
            )

        finished = _utc_now_iso()
        return ActionResult(
            id=aid,
            type=atype,
            title=title,
            status="skipped",
            message=f"unknown action type '{atype}' (skipped)",
            started_at=started,
            finished_at=finished,
            details={"supported_types": ["analysis", "execution"]},
        )

    except Exception as e:
        finished = _utc_now_iso()
        return ActionResult(
            id=aid,
            type=atype,
            title=title,
            status="failed",
            message=str(e),
            started_at=started,
            finished_at=finished,
            details={},
        )


def run_plan(plan_doc: Dict[str, Any], *, execute: bool, confirm: bool) -> Dict[str, Any]:
    _validate_execution_plan(plan_doc)

    results: List[ActionResult] = []
    for action in plan_doc["plan"]:
        results.append(_run_action(action, execute=execute, confirm=confirm))

    total = len(results)
    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped")
    blocked = sum(1 for r in results if r.status == "blocked")
    failed = sum(1 for r in results if r.status == "failed")

    report: Dict[str, Any] = {
        "schema_id": "execution-report",
        "schema_version": "v0",
        "generated_at": _utc_now_iso(),
        "runner": {
            "id": "runner.v0",
            "safe_mode": True,
            "execute_requested": bool(execute),
            "confirm_received": bool(confirm),
        },
        "decision_snapshot": plan_doc.get("decision_snapshot", {}),
        "payload_snapshot": plan_doc.get("payload_snapshot", {}),
        "summary": {
            "total": total,
            "ok": ok,
            "skipped": skipped,
            "blocked": blocked,
            "failed": failed,
            "status": "ok" if failed == 0 else "failed",
        },
        "results": [
            {
                "id": r.id,
                "type": r.type,
                "title": r.title,
                "status": r.status,
                "message": r.message,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "details": r.details,
            }
            for r in results
        ],
    }
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Runner v0 (SAFE) - executes an execution-plan and writes execution-report.")
    ap.add_argument("--plan", required=True, help="Path to execution_plan.json")
    ap.add_argument("--out", required=True, help="Path to write execution_report.json")
    ap.add_argument("--execute", action="store_true", help="Allow execution-phase actions to run (still SAFE in v0).")
    ap.add_argument("--confirm", action="store_true", help="Acknowledge require_user_confirm guardrail.")
    args = ap.parse_args(argv)

    plan_path = Path(args.plan)
    out_path = Path(args.out)

    try:
        doc = _read_json(plan_path)
        report = run_plan(doc, execute=bool(args.execute), confirm=bool(args.confirm))
        _write_json(out_path, report)
        print(f"OK -> wrote: {out_path}")
        # exit non-zero only if failed>0
        return 0 if report["summary"]["failed"] == 0 else 2
    except RunnerError as e:
        print(f"RunnerError: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"UnexpectedError: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
