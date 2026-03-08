from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass
class VerdictRecord:
    rel_path: str
    verdict: str
    confidence: float
    decision_score: float
    reasons: List[str]
    scores_snapshot: Dict[str, float]
    policy_tags: List[str]


class VerdictEngine:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()
        self.scores_path = self.output_dir / "scores.json"
        self.policy_path = self.output_dir / "policy.eval.json"
        self.manifest_path = self.output_dir / "manifest.report.json"
        self.verdict_path = self.output_dir / "verdict.json"

    def validate_inputs(self) -> None:
        if not self.output_dir.exists():
            raise FileNotFoundError("Output dir missing")
        if not self.scores_path.exists():
            raise FileNotFoundError("scores.json missing")
        if not self.policy_path.exists():
            raise FileNotFoundError("policy.eval.json missing")
        if not self.manifest_path.exists():
            raise FileNotFoundError("manifest.report.json missing")

    def build_policy_index(self, policy_eval: dict) -> Dict[str, dict]:
        return {
            r["rel_path"]: r
            for r in policy_eval.get("records", [])
        }

    def compute_decision_score(self, scores: dict) -> float:
        value_score = float(scores["value_score"])
        rebuild_cost_score = float(scores["rebuild_cost_score"])
        cost_to_keep_score = float(scores["cost_to_keep_score"])
        risk_score = float(scores["risk_score"])

        # Weighted decision score
        # Higher means stronger tendency to keep
        return round(
            (value_score * 0.40)
            + (rebuild_cost_score * 0.35)
            - (cost_to_keep_score * 0.15)
            - (risk_score * 0.10),
            3,
        )

    def confidence_from_context(
        self,
        confidence_score: float,
        reasons: List[str],
        policy_tags: List[str],
    ) -> float:
        confidence = confidence_score

        if "LOW_CONFIDENCE" in policy_tags:
            confidence -= 0.20
        if "HIGH_RISK" in policy_tags:
            confidence -= 0.05
        if "KEEP_BIAS" in policy_tags:
            confidence += 0.03
        if "duplicate_low_value" in reasons:
            confidence += 0.05
        if "empty_file" in reasons:
            confidence += 0.08

        return round(clamp01(confidence), 3)

    def evaluate_record(self, score_record: dict, policy_record: dict) -> VerdictRecord:
        rel_path = score_record["rel_path"]
        scores = score_record["scores"]
        flags = score_record["flags"]
        reason_hints = list(score_record.get("reason_hints", []))

        policy_flags = policy_record.get("policy_flags", {})
        policy_tags = list(policy_record.get("policy_tags", []))

        decision_score = self.compute_decision_score(scores)
        reasons: List[str] = []

        review_required = bool(policy_flags.get("review_required", False))
        high_risk = bool(policy_flags.get("high_risk", False))
        duplicate_low_value = bool(policy_flags.get("duplicate_low_value", False))
        empty_file_candidate = bool(policy_flags.get("empty_file_candidate", False))
        keep_bias = bool(policy_flags.get("keep_bias", False))

        verdict = "REVIEW"

        # Priority rules first
        if review_required:
            verdict = "REVIEW"
            reasons.append("review_required")

        elif high_risk and keep_bias:
            verdict = "KEEP"
            reasons.extend(["high_risk_but_keep_bias", "protected_by_keep_bias"])

        elif high_risk and not keep_bias:
            verdict = "REVIEW"
            reasons.append("high_risk_requires_review")

        elif empty_file_candidate and not keep_bias:
            verdict = "DELETE_CANDIDATE"
            reasons.append("empty_file")

        elif duplicate_low_value:
            verdict = "DELETE_CANDIDATE"
            reasons.append("duplicate_low_value")

        else:
            if decision_score >= 1.8:
                verdict = "KEEP"
                reasons.append("high_decision_score")
            elif decision_score >= 1.1:
                verdict = "ARCHIVE"
                reasons.append("medium_decision_score")
            else:
                verdict = "DELETE_CANDIDATE"
                reasons.append("low_decision_score")

        if flags.get("is_code_file", False):
            reasons.append("code_file")
        if flags.get("is_config_file", False):
            reasons.append("config_file")
        if flags.get("is_hidden_file", False):
            reasons.append("hidden_file")
        if flags.get("is_duplicate_candidate", False):
            reasons.append("duplicate_candidate")

        confidence = self.confidence_from_context(
            float(scores["confidence_score"]),
            reasons,
            policy_tags,
        )

        return VerdictRecord(
            rel_path=rel_path,
            verdict=verdict,
            confidence=confidence,
            decision_score=decision_score,
            reasons=sorted(set(reasons + reason_hints)),
            scores_snapshot={
                "risk_score": float(scores["risk_score"]),
                "value_score": float(scores["value_score"]),
                "cost_to_keep_score": float(scores["cost_to_keep_score"]),
                "rebuild_cost_score": float(scores["rebuild_cost_score"]),
                "confidence_score": float(scores["confidence_score"]),
            },
            policy_tags=sorted(set(policy_tags)),
        )

    def build(self) -> dict:
        self.validate_inputs()

        scores = load_json(self.scores_path)
        policy_eval = load_json(self.policy_path)
        _manifest = load_json(self.manifest_path)  # reserved for later richer logic

        policy_index = self.build_policy_index(policy_eval)

        records: List[dict] = []
        summary = {
            "KEEP": 0,
            "REVIEW": 0,
            "ARCHIVE": 0,
            "DELETE_CANDIDATE": 0,
            "HOLD": 0,
            "avg_confidence": 0.0,
            "avg_decision_score": 0.0,
        }

        total_confidence = 0.0
        total_decision_score = 0.0

        for score_record in scores.get("records", []):
            rel_path = score_record["rel_path"]
            policy_record = policy_index.get(
                rel_path,
                {
                    "rel_path": rel_path,
                    "policy_flags": {
                        "review_required": False,
                        "high_risk": False,
                        "duplicate_low_value": False,
                        "empty_file_candidate": False,
                        "keep_bias": False,
                    },
                    "policy_tags": [],
                },
            )

            verdict_record = self.evaluate_record(score_record, policy_record)
            records.append(asdict(verdict_record))

            summary[verdict_record.verdict] += 1
            total_confidence += verdict_record.confidence
            total_decision_score += verdict_record.decision_score

        total = max(1, len(records))
        summary["avg_confidence"] = round(total_confidence / total, 3)
        summary["avg_decision_score"] = round(total_decision_score / total, 3)

        payload = {
            "schema_version": "v1",
            "summary": summary,
            "records": records,
        }

        write_json(self.verdict_path, payload)
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verdict Engine")
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
        engine = VerdictEngine(output_dir)
        payload = engine.build()

        print("VERDICT ENGINE COMPLETE")
        print(f"Total records: {len(payload['records'])}")
        print(f"KEEP: {payload['summary']['KEEP']}")
        print(f"REVIEW: {payload['summary']['REVIEW']}")
        print(f"ARCHIVE: {payload['summary']['ARCHIVE']}")
        print(f"DELETE_CANDIDATE: {payload['summary']['DELETE_CANDIDATE']}")
        print(f"Avg confidence: {payload['summary']['avg_confidence']}")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
