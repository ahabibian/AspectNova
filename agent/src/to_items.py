from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ------------------------------------------------------------
# Normalization Logic
# ------------------------------------------------------------

def guess_type(entry: Dict[str, Any]) -> str:
    if entry.get("is_dir") is True:
        return "FOLDER"

    if entry.get("type") in ("dir", "folder", "directory"):
        return "FOLDER"

    p = (
        entry.get("path")
        or entry.get("relpath")
        or entry.get("name")
        or ""
    ).lower()

    if p.endswith("/") or p.endswith("\\"):
        return "FOLDER"

    return "FILE"


def entry_path(entry: Dict[str, Any]) -> str:
    return (
        entry.get("path")
        or entry.get("relpath")
        or entry.get("name")
        or entry.get("id")
        or ""
    )


def normalize_timestamp(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except Exception:
        return None


def build_item(entry: Dict[str, Any]) -> Dict[str, Any]:
    p = entry_path(entry)
    size = int(entry.get("size_bytes") or entry.get("size") or entry.get("bytes") or 0)
    object_type = guess_type(entry)

    mtime = normalize_timestamp(
        entry.get("mtime_utc")
        or entry.get("modified_utc")
        or entry.get("modified_at")
        or entry.get("mtime")
    )

    atime = normalize_timestamp(
        entry.get("atime_utc")
        or entry.get("last_accessed_utc")
        or entry.get("atime")
    )

    file_count = entry.get("file_count") or entry.get("count")
    try:
        file_count = int(file_count) if file_count is not None else None
    except Exception:
        file_count = None

    return {
        "id": entry.get("id") or entry.get("hash"),
        "path": p,
        "object_type": object_type,
        "size_bytes": size,
        "file_count": file_count,
        "last_modified_utc": mtime,
        "last_accessed_utc": atime,
        "owner": entry.get("owner") or "",
        "business_unit": entry.get("business_unit") or "",
        "tags": entry.get("tags") or [],
        "source": {
            "scanner": "aspectnova-agent",
            "raw": {
                "name": entry.get("name"),
                "ext": entry.get("ext"),
            },
        },
    }


# ------------------------------------------------------------
# Core Convert Function
# ------------------------------------------------------------

def convert_scan_to_items(
    scan_data: Dict[str, Any],
    root_path: str | None = None,
) -> Dict[str, Any]:

    entries: List[Dict[str, Any]] = []

    if isinstance(scan_data.get("entries"), list):
        entries = scan_data["entries"]

    elif isinstance(scan_data.get("files"), list):
        entries = scan_data["files"]

    elif isinstance(scan_data.get("items"), list):
        entries = scan_data["items"]

    else:
        raise ValueError("Unsupported scan format: cannot locate entries")

    items = [build_item(e) for e in entries]

    return {
        "schema_id": "data_verdict.items",
        "schema_version": "v1",
        "generated_at": utc_now(),
        "root_path": root_path,
        "items_count": len(items),
        "items": items,
    }


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Convert AspectNova scan_result to Data Verdict items format")
    parser.add_argument("--in-json", required=True, help="Path to scan_result.json or scan_result.canonical.json")
    parser.add_argument("--out-json", required=True, help="Output path for items.json")
    parser.add_argument("--root", required=False, help="Optional root path label")

    args = parser.parse_args()

    try:
        input_path = Path(args.in_json)
        output_path = Path(args.out_json)

        scan_data = load_json(input_path)

        result = convert_scan_to_items(
            scan_data=scan_data,
            root_path=args.root,
        )

        save_json(output_path, result)

        print(f"[ok] wrote items file: {output_path}")
        print(f"[info] items_count: {result['items_count']}")

        return 0

    except Exception as e:
        print(f"[error] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
