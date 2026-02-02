from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def stable_hash(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def as_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: build_command_plan.py <cleanup_proposal.json> <out_command_plan.json>")
        return 2

    proposal_path = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()

    proposal = read_json(proposal_path)

    schema_id = proposal.get("schema_id", "aspectnova.cleanup_proposal")
    schema_version = proposal.get("schema_version", "aspectnova.cleanup_proposal.v1")
    meta = proposal.get("meta") or {}
    proposal_id = meta.get("proposal_id") or "proposal-unknown"

    actions = as_list((proposal.get("proposal") or {}).get("actions"))

    commands: List[Dict[str, Any]] = []

    # Map proposal action types -> command types
    # (فعلاً فقط چیزی که تو تست‌ها می‌خوایم)
    ACTION_MAP = {
        "cleanup.candidates.v1": "ARCHIVE",
    }

    for a in actions:
        action_type = (a or {}).get("action_type")
        cmd_type = ACTION_MAP.get(action_type)
        if not cmd_type:
            continue

        targets = as_list((a or {}).get("targets"))
        for t in targets:
            kind = (t or {}).get("kind")
            path = (t or {}).get("path")

            if kind != "DIRECTORY" or not path:
                continue

            commands.append(
                {
                    "command_id": f"cmd-{stable_hash({'proposal_id': proposal_id, 'type': cmd_type, 'path': path})[:24]}",
                    "type": cmd_type,
                    "target": {"scope": "DIRECTORY", "ref": path},
                    "risk_level": "MEDIUM",
                    "confidence": 0.7,
                }
            )

    # اگر هیچ فرمانی قابل ساخت نبود، NOOP اما باز هم plan_key باید داشته باشد
    if not commands:
        commands = [
            {
                "command_id": f"cmd-{stable_hash({'proposal_id': proposal_id, 'type': 'NOOP'})[:24]}",
                "type": "NOOP",
                "target": {"scope": "PROPOSAL", "ref": proposal_id},
                "risk_level": "LOW",
                "confidence": 1.0,
                "message": "No executable commands produced from proposal.",
            }
        ]

    # idempotency.plan_key باید همیشه set شود (حتی برای NOOP)
    plan_key = stable_hash(
        {
            "schema_id": "aspectnova.command_plan",
            "schema_version": "v1",
            "proposal_id": proposal_id,
            "commands": commands,
        }
    )

    plan = {
        "schema_id": "aspectnova.command_plan",
        "schema_version": "v1",
        "meta": {
            "generated_at": meta.get("generated_at") or "",
            "source_proposal_id": proposal_id,
        },
        "idempotency": {
            "plan_key": plan_key,
        },
        "commands": commands,
    }

    write_json(out_path, plan)
    print(f"[build_command_plan] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
