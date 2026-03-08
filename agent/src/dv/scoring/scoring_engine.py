from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set


CODE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".cpp", ".c",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".lua",
    ".sh", ".ps1", ".cmd", ".bat",
}

CONFIG_EXTENSIONS: Set[str] = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".xml",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clamp(value: float, min_value: float = 0.0, max_value: float = 5.0) -> float:
    return max(min_value, min(max_value, value))


def parse_iso_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class FileFlags:
    is_duplicate_candidate: bool
    is_large_file: bool
    is_old_file: bool
    is_hidden_file: bool
    is_empty_file: bool
    is_code_file: bool
    is_config_file: bool


@dataclass
class FileScores:
    risk_score: float
    value_score: float
    cost_to_keep_score: float
    rebuild_cost_score: float
    confidence_score: float


@dataclass
class FileScoreRecord:
    rel_path: str
    extension: str
    mime_type: str
    size_bytes: int
    flags: FileFlags
    scores: FileScores
    reason_hints: List[str]


class ScoringEngine:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()
        self.inventory_path = self.output_dir / "inventory.json"
        self.manifest_path = self.output_dir / "manifest.report.json"
        self.scores_path = self.output_dir / "scores.json"

    def validate_inputs(self) -> None:
        if not self.output_dir.exists():
            raise FileNotFoundError(f"Output directory does not exist: {self.output_dir}")
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"inventory.json not found: {self.inventory_path}")
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"manifest.report.json not found: {self.manifest_path}")

    def build_duplicate_path_set(self, manifest: dict) -> Set[str]:
        result: Set[str] = set()
        for group in manifest.get("duplicate_hash_candidates", []):
            for rel_path in group.get("files", []):
                result.add(rel_path)
        return result

    def score_file(self, item: Dict[str, Any], duplicate_paths: Set[str]) -> FileScoreRecord:
        rel_path = item.get("rel_path", "")
        extension = (item.get("extension") or "").lower()
        mime_type = item.get("mime_type", "application/octet-stream")
        size_bytes = int(item.get("size_bytes", 0))
        modified_at = item.get("modified_at_utc")
        is_hidden = bool(item.get("is_hidden", False))
        sha256 = item.get("sha256")

        now = datetime.now(timezone.utc)
        age_days = 0.0
        if modified_at:
            try:
                age_days = (now - parse_iso_utc(modified_at)).total_seconds() / 86400
            except Exception:
                age_days = 0.0

        is_duplicate_candidate = rel_path in duplicate_paths
        is_large_file = size_bytes >= 25 * 1024 * 1024
        is_old_file = age_days >= 365
        is_empty_file = size_bytes == 0
        is_code_file = extension in CODE_EXTENSIONS
        is_config_file = extension in CONFIG_EXTENSIONS

        flags = FileFlags(
            is_duplicate_candidate=is_duplicate_candidate,
            is_large_file=is_large_file,
            is_old_file=is_old_file,
            is_hidden_file=is_hidden,
            is_empty_file=is_empty_file,
            is_code_file=is_code_file,
            is_config_file=is_config_file,
        )

        reason_hints: List[str] = []

        # risk_score
        risk_score = 0.5
        if is_hidden:
            risk_score += 0.5
            reason_hints.append("hidden_file")
        if extension in {".exe", ".dll", ".bat", ".cmd", ".ps1"}:
            risk_score += 1.0
            reason_hints.append("executable_or_script")
        if mime_type == "application/octet-stream":
            risk_score += 0.4
            reason_hints.append("generic_binary_or_unknown")
        if is_duplicate_candidate:
            risk_score += 0.2
            reason_hints.append("duplicate_candidate")

        # value_score
        value_score = 1.0
        if is_code_file:
            value_score += 2.0
            reason_hints.append("code_asset")
        if is_config_file:
            value_score += 1.2
            reason_hints.append("config_asset")
        if extension in {".md", ".txt"}:
            value_score += 0.6
            reason_hints.append("documentation_or_text")
        if is_old_file:
            value_score -= 0.4
            reason_hints.append("old_file")

        # cost_to_keep_score
        cost_to_keep_score = 0.2
        if size_bytes >= 1 * 1024 * 1024:
            cost_to_keep_score += 1.0
            reason_hints.append("medium_or_large_size")
        if size_bytes >= 10 * 1024 * 1024:
            cost_to_keep_score += 1.5
        if is_large_file:
            cost_to_keep_score += 1.5
            reason_hints.append("large_file")
        if is_duplicate_candidate:
            cost_to_keep_score += 1.0

        # rebuild_cost_score
        rebuild_cost_score = 0.5
        if is_code_file:
            rebuild_cost_score += 2.0
        if is_config_file:
            rebuild_cost_score += 1.5
        if extension in {".json", ".yaml", ".yml", ".toml"}:
            rebuild_cost_score += 0.7
        if is_empty_file:
            rebuild_cost_score -= 0.4
            reason_hints.append("empty_file")
        if is_duplicate_candidate:
            rebuild_cost_score -= 0.5

        # confidence_score (0..1)
        confidence_score = 0.9
        if not sha256:
            confidence_score -= 0.2
            reason_hints.append("missing_hash")
        if mime_type == "application/octet-stream":
            confidence_score -= 0.15
        if extension == "":
            confidence_score -= 0.15
            reason_hints.append("missing_extension")
        if is_hidden:
            confidence_score -= 0.05

        scores = FileScores(
            risk_score=round(clamp(risk_score), 3),
            value_score=round(clamp(value_score), 3),
            cost_to_keep_score=round(clamp(cost_to_keep_score), 3),
            rebuild_cost_score=round(clamp(rebuild_cost_score), 3),
            confidence_score=round(max(0.0, min(1.0, confidence_score)), 3),
        )

        return FileScoreRecord(
            rel_path=rel_path,
            extension=extension,
            mime_type=mime_type,
            size_bytes=size_bytes,
            flags=flags,
            scores=scores,
            reason_hints=sorted(set(reason_hints)),
        )

    def build(self) -> dict:
        self.validate_inputs()

        inventory = load_json(self.inventory_path)
        manifest = load_json(self.manifest_path)
        files = inventory.get("files", [])

        duplicate_paths = self.build_duplicate_path_set(manifest)

        records: List[dict] = []
        aggregate = {
            "avg_risk_score": 0.0,
            "avg_value_score": 0.0,
            "avg_cost_to_keep_score": 0.0,
            "avg_rebuild_cost_score": 0.0,
            "avg_confidence_score": 0.0,
            "duplicate_candidates": 0,
            "large_files": 0,
            "old_files": 0,
            "hidden_files": 0,
            "empty_files": 0,
            "code_files": 0,
            "config_files": 0,
        }

        score_totals = {
            "risk_score": 0.0,
            "value_score": 0.0,
            "cost_to_keep_score": 0.0,
            "rebuild_cost_score": 0.0,
            "confidence_score": 0.0,
        }

        for item in sorted(files, key=lambda x: x.get("rel_path", "")):
            record = self.score_file(item, duplicate_paths)
            records.append(asdict(record))

            score_totals["risk_score"] += record.scores.risk_score
            score_totals["value_score"] += record.scores.value_score
            score_totals["cost_to_keep_score"] += record.scores.cost_to_keep_score
            score_totals["rebuild_cost_score"] += record.scores.rebuild_cost_score
            score_totals["confidence_score"] += record.scores.confidence_score

            aggregate["duplicate_candidates"] += int(record.flags.is_duplicate_candidate)
            aggregate["large_files"] += int(record.flags.is_large_file)
            aggregate["old_files"] += int(record.flags.is_old_file)
            aggregate["hidden_files"] += int(record.flags.is_hidden_file)
            aggregate["empty_files"] += int(record.flags.is_empty_file)
            aggregate["code_files"] += int(record.flags.is_code_file)
            aggregate["config_files"] += int(record.flags.is_config_file)

        total = max(1, len(records))
        aggregate["avg_risk_score"] = round(score_totals["risk_score"] / total, 3)
        aggregate["avg_value_score"] = round(score_totals["value_score"] / total, 3)
        aggregate["avg_cost_to_keep_score"] = round(score_totals["cost_to_keep_score"] / total, 3)
        aggregate["avg_rebuild_cost_score"] = round(score_totals["rebuild_cost_score"] / total, 3)
        aggregate["avg_confidence_score"] = round(score_totals["confidence_score"] / total, 3)

        payload = {
            "schema_version": "v1",
            "generated_at_utc": utc_now_iso(),
            "source_files": {
                "inventory": str(self.inventory_path),
                "manifest_report": str(self.manifest_path),
            },
            "summary": {
                "total_files": len(records),
                **aggregate,
            },
            "records": records,
        }

        write_json(self.scores_path, payload)
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build scores.json from DV inventory and manifest")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Path to DV run output directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)

    try:
        engine = ScoringEngine(output_dir=output_dir)
        payload = engine.build()

        print("SCORING COMPLETE")
        print(f"Output dir: {output_dir}")
        print(f"Scores file: {output_dir / 'scores.json'}")
        print(f"Total files: {payload['summary']['total_files']}")
        print(f"Avg risk score: {payload['summary']['avg_risk_score']}")
        print(f"Avg value score: {payload['summary']['avg_value_score']}")
        print(f"Duplicate candidates: {payload['summary']['duplicate_candidates']}")
        return 0

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
