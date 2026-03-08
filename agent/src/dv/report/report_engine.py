from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def top_n_from_mapping(mapping: Dict[str, int], n: int = 10) -> List[Dict[str, Any]]:
    items = sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"key": k, "count": v} for k, v in items[:n]]


class ReportEngine:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()

        self.inventory_path = self.output_dir / "inventory.json"
        self.manifest_path = self.output_dir / "manifest.report.json"
        self.scores_path = self.output_dir / "scores.json"
        self.policy_path = self.output_dir / "policy.eval.json"
        self.verdict_path = self.output_dir / "verdict.json"
        self.run_meta_path = self.output_dir / "run.meta.json"

        self.report_json_path = self.output_dir / "dv_report.json"
        self.report_md_path = self.output_dir / "dv_report.md"

    def validate_inputs(self) -> None:
        required = [
            self.inventory_path,
            self.manifest_path,
            self.scores_path,
            self.policy_path,
            self.verdict_path,
            self.run_meta_path,
        ]
        for path in required:
            if not path.exists():
                raise FileNotFoundError(f"Required input missing: {path}")

    def build_waste_score(self, verdict_summary: dict, manifest_summary: dict) -> Dict[str, Any]:
        total_files = max(1, int(verdict_summary.get("KEEP", 0))
                             + int(verdict_summary.get("ARCHIVE", 0))
                             + int(verdict_summary.get("DELETE_CANDIDATE", 0))
                             + int(verdict_summary.get("REVIEW", 0))
                             + int(verdict_summary.get("HOLD", 0)))

        delete_count = int(verdict_summary.get("DELETE_CANDIDATE", 0))
        archive_count = int(verdict_summary.get("ARCHIVE", 0))
        review_count = int(verdict_summary.get("REVIEW", 0))
        duplicate_groups = len(manifest_summary.get("duplicate_hash_candidates", []))

        cleanup_opportunity_pct = round(((delete_count + archive_count) / total_files) * 100, 2)
        review_pressure_pct = round((review_count / total_files) * 100, 2)

        raw_score = (
            (delete_count * 1.0)
            + (archive_count * 0.6)
            + (review_count * 0.8)
            + (duplicate_groups * 0.4)
        ) / total_files * 100.0

        waste_score = round(min(100.0, raw_score), 2)

        if waste_score >= 60:
            band = "HIGH"
        elif waste_score >= 30:
            band = "MEDIUM"
        else:
            band = "LOW"

        return {
            "waste_score": waste_score,
            "waste_band": band,
            "cleanup_opportunity_pct": cleanup_opportunity_pct,
            "review_pressure_pct": review_pressure_pct,
        }

    def build(self) -> dict:
        self.validate_inputs()

        inventory = load_json(self.inventory_path)
        manifest = load_json(self.manifest_path)
        scores = load_json(self.scores_path)
        policy_eval = load_json(self.policy_path)
        verdict = load_json(self.verdict_path)
        run_meta = load_json(self.run_meta_path)

        inventory_files = inventory.get("files", [])
        manifest_summary = manifest.get("summary", {})
        manifest_distributions = manifest.get("distributions", {})
        largest_files = manifest.get("largest_files_top20", [])
        duplicate_candidates = manifest.get("duplicate_hash_candidates", [])

        score_summary = scores.get("summary", {})
        policy_summary = policy_eval.get("summary", {})
        verdict_summary = verdict.get("summary", {})

        review_records = [
            r for r in verdict.get("records", [])
            if r.get("verdict") == "REVIEW"
        ][:20]

        delete_records = [
            r for r in verdict.get("records", [])
            if r.get("verdict") == "DELETE_CANDIDATE"
        ][:20]

        archive_records = [
            r for r in verdict.get("records", [])
            if r.get("verdict") == "ARCHIVE"
        ][:20]

        keep_records = [
            r for r in verdict.get("records", [])
            if r.get("verdict") == "KEEP"
        ][:20]

        waste = self.build_waste_score(verdict_summary, manifest)

        report = {
            "schema_version": "v1",
            "generated_at_utc": utc_now_iso(),
            "run": {
                "run_id": run_meta.get("run_id"),
                "workspace_root": run_meta.get("workspace_root"),
                "started_at_utc": run_meta.get("started_at_utc"),
                "finished_at_utc": run_meta.get("finished_at_utc"),
                "scanner_version": run_meta.get("scanner_version"),
            },
            "executive_summary": {
                "total_files": len(inventory_files),
                "total_size_bytes": manifest_summary.get("total_size_bytes", 0),
                "keep_count": verdict_summary.get("KEEP", 0),
                "archive_count": verdict_summary.get("ARCHIVE", 0),
                "delete_candidate_count": verdict_summary.get("DELETE_CANDIDATE", 0),
                "review_count": verdict_summary.get("REVIEW", 0),
                "avg_confidence": verdict_summary.get("avg_confidence", 0.0),
                **waste,
            },
            "technical_summary": {
                "hidden_files": manifest_summary.get("hidden_files", 0),
                "symlink_files": manifest_summary.get("symlink_files", 0),
                "hashed_files": manifest_summary.get("hashed_files", 0),
                "unhashed_files": manifest_summary.get("unhashed_files", 0),
                "distinct_extensions": manifest_summary.get("distinct_extensions", 0),
                "distinct_mime_types": manifest_summary.get("distinct_mime_types", 0),
                "duplicate_group_count": len(duplicate_candidates),
                "largest_files_top20": largest_files,
                "top_extensions": top_n_from_mapping(manifest_distributions.get("extensions", {}), 10),
                "top_mime_types": top_n_from_mapping(manifest_distributions.get("mime_types", {}), 10),
                "age_buckets": manifest_distributions.get("age_buckets", {}),
            },
            "scoring_summary": score_summary,
            "policy_summary": policy_summary,
            "verdict_summary": verdict_summary,
            "action_summary": {
                "review_required_top20": review_records,
                "delete_candidates_top20": delete_records,
                "archive_candidates_top20": archive_records,
                "keep_assets_top20": keep_records,
            },
            "observations": [
                "This DV report is based on deterministic scan, manifest, scoring, policy, and verdict stages.",
                "DELETE_CANDIDATE does not imply automatic deletion. It is a dry-run recommendation only.",
                "REVIEW indicates items that should be checked by a human due to low confidence or risk-sensitive context.",
            ],
        }

        write_json(self.report_json_path, report)
        write_text(self.report_md_path, self.render_markdown(report))

        return report

    def render_markdown(self, report: dict) -> str:
        exec_summary = report["executive_summary"]
        tech = report["technical_summary"]
        scoring = report["scoring_summary"]
        policy = report["policy_summary"]
        verdict = report["verdict_summary"]

        lines: List[str] = []
        lines.append("# Data Verdict Report")
        lines.append("")
        lines.append(f"- Run ID: `{report['run']['run_id']}`")
        lines.append(f"- Workspace: `{report['run']['workspace_root']}`")
        lines.append(f"- Generated at: `{report['generated_at_utc']}`")
        lines.append("")

        lines.append("## Executive Summary")
        lines.append("")
        lines.append(f"- Total files: **{exec_summary['total_files']}**")
        lines.append(f"- Total size (bytes): **{exec_summary['total_size_bytes']}**")
        lines.append(f"- KEEP: **{exec_summary['keep_count']}**")
        lines.append(f"- ARCHIVE: **{exec_summary['archive_count']}**")
        lines.append(f"- DELETE_CANDIDATE: **{exec_summary['delete_candidate_count']}**")
        lines.append(f"- REVIEW: **{exec_summary['review_count']}**")
        lines.append(f"- Average confidence: **{exec_summary['avg_confidence']}**")
        lines.append(f"- Waste score: **{exec_summary['waste_score']}** ({exec_summary['waste_band']})")
        lines.append(f"- Cleanup opportunity: **{exec_summary['cleanup_opportunity_pct']}%**")
        lines.append("")

        lines.append("## Technical Summary")
        lines.append("")
        lines.append(f"- Hidden files: **{tech['hidden_files']}**")
        lines.append(f"- Symlink files: **{tech['symlink_files']}**")
        lines.append(f"- Duplicate groups: **{tech['duplicate_group_count']}**")
        lines.append(f"- Distinct extensions: **{tech['distinct_extensions']}**")
        lines.append(f"- Distinct mime types: **{tech['distinct_mime_types']}**")
        lines.append("")

        lines.append("## Scoring Summary")
        lines.append("")
        lines.append(f"- Avg risk score: **{scoring.get('avg_risk_score', 0)}**")
        lines.append(f"- Avg value score: **{scoring.get('avg_value_score', 0)}**")
        lines.append(f"- Avg cost-to-keep score: **{scoring.get('avg_cost_to_keep_score', 0)}**")
        lines.append(f"- Avg rebuild cost score: **{scoring.get('avg_rebuild_cost_score', 0)}**")
        lines.append("")

        lines.append("## Policy Summary")
        lines.append("")
        lines.append(f"- Review required: **{policy.get('review_required', 0)}**")
        lines.append(f"- High risk: **{policy.get('high_risk', 0)}**")
        lines.append(f"- Duplicate low value: **{policy.get('duplicate_low_value', 0)}**")
        lines.append(f"- Empty file: **{policy.get('empty_file', 0)}**")
        lines.append(f"- Keep bias: **{policy.get('keep_bias', 0)}**")
        lines.append("")

        lines.append("## Verdict Summary")
        lines.append("")
        lines.append(f"- KEEP: **{verdict.get('KEEP', 0)}**")
        lines.append(f"- ARCHIVE: **{verdict.get('ARCHIVE', 0)}**")
        lines.append(f"- DELETE_CANDIDATE: **{verdict.get('DELETE_CANDIDATE', 0)}**")
        lines.append(f"- REVIEW: **{verdict.get('REVIEW', 0)}**")
        lines.append(f"- Average decision score: **{verdict.get('avg_decision_score', 0)}**")
        lines.append("")

        lines.append("## Top Extensions")
        lines.append("")
        for item in tech["top_extensions"]:
            lines.append(f"- `{item['key']}` → {item['count']}")
        lines.append("")

        lines.append("## Top Mime Types")
        lines.append("")
        for item in tech["top_mime_types"]:
            lines.append(f"- `{item['key']}` → {item['count']}")
        lines.append("")

        lines.append("## Notes")
        lines.append("")
        for obs in report["observations"]:
            lines.append(f"- {obs}")
        lines.append("")

        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DV Report Engine")
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
        engine = ReportEngine(output_dir)
        report = engine.build()

        print("REPORT ENGINE COMPLETE")
        print(f"Report JSON: {output_dir / 'dv_report.json'}")
        print(f"Report MD:   {output_dir / 'dv_report.md'}")
        print(f"Waste score: {report['executive_summary']['waste_score']}")
        print(f"Cleanup opportunity: {report['executive_summary']['cleanup_opportunity_pct']}%")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
