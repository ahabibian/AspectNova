from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@dataclass
class PlannedAction:
    rel_path: str
    verdict: str
    proposed_action: str
    execution_stage: str
    dry_run: bool
    approval_required: bool
    rollback_possible: bool
    priority: str
    confidence: float
    decision_score: float
    target_zone: str | None
    delete_after_approval: bool
    policy_tags: List[str]
    reason_summary: List[str]


class CleanupPlanner:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()
        self.verdict_path = self.output_dir / "verdict.json"
        self.plan_path = self.output_dir / "cleanup_plan.json"

    def validate_inputs(self) -> None:
        if not self.output_dir.exists():
            raise FileNotFoundError("Output dir missing")
        if not self.verdict_path.exists():
            raise FileNotFoundError("verdict.json missing")

    def is_documentation(self, rel_path: str) -> bool:
        p = rel_path.lower()
        return (
            p.startswith("docs/")
            or "/docs/" in p
            or p.startswith("readme")
            or p.endswith("/readme.md")
            or p.endswith(".md")
            or "adr-" in p
        )

    def map_verdict_to_action(self, record: Dict[str, Any]) -> PlannedAction:
        rel_path = record["rel_path"]
        verdict = record["verdict"]
        confidence = float(record.get("confidence", 0.0))
        decision_score = float(record.get("decision_score", 0.0))
        policy_tags = list(record.get("policy_tags", []))
        reasons = list(record.get("reasons", []))

        proposed_action = "manual_review"
        execution_stage = "human_review"
        approval_required = True
        rollback_possible = False
        priority = "normal"
        target_zone = None
        delete_after_approval = False

        # Documentation safeguard
        if verdict == "DELETE_CANDIDATE" and self.is_documentation(rel_path):
            verdict = "ARCHIVE"
            reasons = sorted(set(reasons + ["documentation_safeguard"]))
            if "LOW_CONFIDENCE" not in policy_tags:
                policy_tags = sorted(set(policy_tags + ["DOC_SAFEGUARD"]))

        if verdict == "KEEP":
            proposed_action = "keep"
            execution_stage = "none"
            approval_required = False
            rollback_possible = False
            priority = "low"

        elif verdict == "ARCHIVE":
            proposed_action = "archive"
            execution_stage = "archive_stage"
            approval_required = True
            rollback_possible = True
            priority = "normal"
            target_zone = "archive"

        elif verdict == "DELETE_CANDIDATE":
            proposed_action = "quarantine_candidate"
            execution_stage = "quarantine_stage"
            approval_required = True
            rollback_possible = True
            priority = "high"
            target_zone = "quarantine"
            delete_after_approval = True

        elif verdict == "REVIEW":
            proposed_action = "manual_review"
            execution_stage = "human_review"
            approval_required = True
            rollback_possible = False
            priority = "high"

        elif verdict == "HOLD":
            proposed_action = "hold"
            execution_stage = "hold_stage"
            approval_required = True
            rollback_possible = False
            priority = "critical"
            target_zone = "hold"

        if "HIGH_RISK" in policy_tags:
            priority = "high"

        if verdict == "REVIEW":
            priority = "high"

        if verdict == "KEEP" and confidence >= 0.9:
            priority = "low"

        return PlannedAction(
            rel_path=rel_path,
            verdict=verdict,
            proposed_action=proposed_action,
            execution_stage=execution_stage,
            dry_run=True,
            approval_required=approval_required,
            rollback_possible=rollback_possible,
            priority=priority,
            confidence=confidence,
            decision_score=decision_score,
            target_zone=target_zone,
            delete_after_approval=delete_after_approval,
            policy_tags=policy_tags,
            reason_summary=reasons[:12],
        )

    def build(self) -> dict:
        self.validate_inputs()

        verdict = load_json(self.verdict_path)
        records = verdict.get("records", [])

        planned_actions: List[dict] = []
        summary = {
            "keep": 0,
            "archive": 0,
            "quarantine_candidate": 0,
            "manual_review": 0,
            "hold": 0,
            "approval_required": 0,
            "high_priority": 0,
            "critical_priority": 0,
            "rollback_possible": 0,
            "documentation_safeguard_promotions": 0,
        }

        for record in records:
            original_verdict = record["verdict"]
            action = self.map_verdict_to_action(record)
            planned_actions.append(asdict(action))

            summary[action.proposed_action] += 1

            if action.approval_required:
                summary["approval_required"] += 1

            if action.priority == "high":
                summary["high_priority"] += 1

            if action.priority == "critical":
                summary["critical_priority"] += 1

            if action.rollback_possible:
                summary["rollback_possible"] += 1

            if original_verdict == "DELETE_CANDIDATE" and action.verdict == "ARCHIVE":
                summary["documentation_safeguard_promotions"] += 1

        payload = {
            "schema_version": "v1",
            "mode": "dry_run",
            "execution_model": "quarantine_then_approval_then_delete",
            "summary": summary,
            "actions": planned_actions,
        }

        write_json(self.plan_path, payload)
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup Planner")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="DV run output directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)

    try:
        planner = CleanupPlanner(output_dir)
        payload = planner.build()

        print("CLEANUP PLANNER COMPLETE")
        print(f"Actions total: {len(payload['actions'])}")
        print(f"Keep: {payload['summary']['keep']}")
        print(f"Archive: {payload['summary']['archive']}")
        print(f"Quarantine candidate: {payload['summary']['quarantine_candidate']}")
        print(f"Manual review: {payload['summary']['manual_review']}")
        print(f"Approval required: {payload['summary']['approval_required']}")
        print(f"Doc safeguard promotions: {payload['summary']['documentation_safeguard_promotions']}")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
