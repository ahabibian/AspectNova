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
class PolicyFlags:
    review_required: bool
    high_risk: bool
    duplicate_low_value: bool
    empty_file_candidate: bool
    keep_bias: bool


@dataclass
class PolicyRecord:
    rel_path: str
    policy_flags: PolicyFlags
    policy_tags: List[str]


class PolicyEngine:

    def __init__(self, output_dir: Path) -> None:

        self.output_dir = output_dir.resolve()
        self.scores_path = self.output_dir / "scores.json"
        self.policy_path = self.output_dir / "policy.eval.json"

    def validate_inputs(self) -> None:

        if not self.output_dir.exists():
            raise FileNotFoundError("Output dir missing")

        if not self.scores_path.exists():
            raise FileNotFoundError("scores.json missing")

    def evaluate_record(self, record: Dict[str, Any]) -> PolicyRecord:

        rel_path = record["rel_path"]
        scores = record["scores"]
        flags = record["flags"]

        risk = scores["risk_score"]
        value = scores["value_score"]
        confidence = scores["confidence_score"]

        policy_tags: List[str] = []

        review_required = False
        high_risk = False
        duplicate_low_value = False
        empty_file_candidate = False
        keep_bias = False

        if confidence < 0.6:
            review_required = True
            policy_tags.append("LOW_CONFIDENCE")

        if risk >= 1.5:
            high_risk = True
            policy_tags.append("HIGH_RISK")

        if flags["is_duplicate_candidate"] and value < 1.5:
            duplicate_low_value = True
            policy_tags.append("DUPLICATE_LOW_VALUE")

        if flags["is_empty_file"]:
            empty_file_candidate = True
            policy_tags.append("EMPTY_FILE")

        if flags["is_code_file"] or flags["is_config_file"]:
            keep_bias = True
            policy_tags.append("KEEP_BIAS")

        return PolicyRecord(
            rel_path=rel_path,
            policy_flags=PolicyFlags(
                review_required=review_required,
                high_risk=high_risk,
                duplicate_low_value=duplicate_low_value,
                empty_file_candidate=empty_file_candidate,
                keep_bias=keep_bias,
            ),
            policy_tags=policy_tags,
        )

    def build(self) -> dict:

        self.validate_inputs()

        scores = load_json(self.scores_path)

        records = scores["records"]

        results: List[dict] = []

        stats = {
            "review_required": 0,
            "high_risk": 0,
            "duplicate_low_value": 0,
            "empty_file": 0,
            "keep_bias": 0,
        }

        for r in records:

            policy = self.evaluate_record(r)

            results.append(asdict(policy))

            if policy.policy_flags.review_required:
                stats["review_required"] += 1

            if policy.policy_flags.high_risk:
                stats["high_risk"] += 1

            if policy.policy_flags.duplicate_low_value:
                stats["duplicate_low_value"] += 1

            if policy.policy_flags.empty_file_candidate:
                stats["empty_file"] += 1

            if policy.policy_flags.keep_bias:
                stats["keep_bias"] += 1

        payload = {
            "schema_version": "v1",
            "summary": stats,
            "records": results,
        }

        write_json(self.policy_path, payload)

        return payload


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(description="Policy Engine")

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

        engine = PolicyEngine(output_dir)

        payload = engine.build()

        print("POLICY ENGINE COMPLETE")

        print(f"Total records: {len(payload['records'])}")

        print(f"Review required: {payload['summary']['review_required']}")

        print(f"High risk: {payload['summary']['high_risk']}")

        print(f"Duplicate low value: {payload['summary']['duplicate_low_value']}")

        return 0

    except Exception as e:

        print(f"ERROR: {e}", file=sys.stderr)

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
