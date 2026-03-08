from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
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


def bucket_age_days(age_days: float) -> str:
    if age_days <= 30:
        return "0_30_days"
    if age_days <= 90:
        return "31_90_days"
    if age_days <= 180:
        return "91_180_days"
    if age_days <= 365:
        return "181_365_days"
    if age_days <= 730:
        return "1_2_years"
    return "2_plus_years"


def parse_iso_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class LargestFileItem:
    rel_path: str
    size_bytes: int
    extension: str
    mime_type: str


@dataclass
class DuplicateHashGroup:
    sha256: str
    file_count: int
    total_size_bytes: int
    files: List[str]


@dataclass
class ManifestSummary:
    total_files: int
    total_size_bytes: int
    hidden_files: int
    symlink_files: int
    hashed_files: int
    unhashed_files: int
    distinct_extensions: int
    distinct_mime_types: int
    generated_at_utc: str


class ManifestBuilder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir.resolve()
        self.inventory_path = self.output_dir / "inventory.json"
        self.run_meta_path = self.output_dir / "run.meta.json"
        self.manifest_path = self.output_dir / "manifest.report.json"

    def validate_inputs(self) -> None:
        if not self.output_dir.exists():
            raise FileNotFoundError(f"Output directory does not exist: {self.output_dir}")
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"inventory.json not found: {self.inventory_path}")
        if not self.run_meta_path.exists():
            raise FileNotFoundError(f"run.meta.json not found: {self.run_meta_path}")

    def build(self) -> dict:
        self.validate_inputs()

        inventory = load_json(self.inventory_path)
        run_meta = load_json(self.run_meta_path)

        files: List[Dict[str, Any]] = inventory.get("files", [])
        now = datetime.now(timezone.utc)

        ext_counter: Counter[str] = Counter()
        mime_counter: Counter[str] = Counter()
        age_bucket_counter: Counter[str] = Counter()
        duplicate_groups: defaultdict[str, List[Dict[str, Any]]] = defaultdict(list)

        total_size_bytes = 0
        hidden_files = 0
        symlink_files = 0
        hashed_files = 0
        unhashed_files = 0

        largest_files: List[Dict[str, Any]] = []

        for item in files:
            rel_path = item.get("rel_path", "")
            size_bytes = int(item.get("size_bytes", 0))
            extension = item.get("extension", "") or ""
            mime_type = item.get("mime_type", "application/octet-stream")
            modified_at = item.get("modified_at_utc")
            sha256 = item.get("sha256")

            total_size_bytes += size_bytes
            ext_counter[extension] += 1
            mime_counter[mime_type] += 1

            if item.get("is_hidden", False):
                hidden_files += 1
            if item.get("is_symlink", False):
                symlink_files += 1

            if sha256:
                hashed_files += 1
                duplicate_groups[sha256].append(item)
            else:
                unhashed_files += 1

            if modified_at:
                try:
                    modified_dt = parse_iso_utc(modified_at)
                    age_days = (now - modified_dt).total_seconds() / 86400
                    age_bucket_counter[bucket_age_days(age_days)] += 1
                except Exception:
                    age_bucket_counter["unknown"] += 1
            else:
                age_bucket_counter["unknown"] += 1

            largest_files.append(
                {
                    "rel_path": rel_path,
                    "size_bytes": size_bytes,
                    "extension": extension,
                    "mime_type": mime_type,
                }
            )

        largest_files_sorted = sorted(
            largest_files,
            key=lambda x: (-x["size_bytes"], x["rel_path"]),
        )[:20]

        duplicate_candidates: List[Dict[str, Any]] = []
        for sha, items in sorted(duplicate_groups.items(), key=lambda kv: kv[0]):
            if len(items) < 2:
                continue

            sorted_items = sorted(items, key=lambda x: x.get("rel_path", ""))
            duplicate_candidates.append(
                asdict(
                    DuplicateHashGroup(
                        sha256=sha,
                        file_count=len(sorted_items),
                        total_size_bytes=sum(int(i.get("size_bytes", 0)) for i in sorted_items),
                        files=[i.get("rel_path", "") for i in sorted_items],
                    )
                )
            )

        summary = asdict(
            ManifestSummary(
                total_files=len(files),
                total_size_bytes=total_size_bytes,
                hidden_files=hidden_files,
                symlink_files=symlink_files,
                hashed_files=hashed_files,
                unhashed_files=unhashed_files,
                distinct_extensions=len(ext_counter),
                distinct_mime_types=len(mime_counter),
                generated_at_utc=utc_now_iso(),
            )
        )

        payload = {
            "schema_version": "v1",
            "run_id": run_meta.get("run_id"),
            "workspace_root": run_meta.get("workspace_root"),
            "generated_at_utc": utc_now_iso(),
            "summary": summary,
            "distributions": {
                "extensions": dict(sorted(ext_counter.items(), key=lambda kv: (kv[0], kv[1]))),
                "mime_types": dict(sorted(mime_counter.items(), key=lambda kv: (kv[0], kv[1]))),
                "age_buckets": dict(sorted(age_bucket_counter.items(), key=lambda kv: kv[0])),
            },
            "largest_files_top20": largest_files_sorted,
            "duplicate_hash_candidates": duplicate_candidates,
            "data_fingerprint": {
                "total_files": len(files),
                "total_size_bytes": total_size_bytes,
                "hashed_files": hashed_files,
                "top_extension": ext_counter.most_common(1)[0][0] if ext_counter else "",
                "top_mime_type": mime_counter.most_common(1)[0][0] if mime_counter else "",
            },
        }

        write_json(self.manifest_path, payload)
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build manifest.report.json from DV inventory")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Path to DV run output directory (contains inventory.json and run.meta.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)

    try:
        builder = ManifestBuilder(output_dir=output_dir)
        payload = builder.build()

        print("MANIFEST BUILD COMPLETE")
        print(f"Output dir: {output_dir}")
        print(f"Manifest: {output_dir / 'manifest.report.json'}")
        print(f"Total files: {payload['summary']['total_files']}")
        print(f"Total size bytes: {payload['summary']['total_size_bytes']}")
        print(f"Duplicate groups: {len(payload['duplicate_hash_candidates'])}")
        return 0

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
