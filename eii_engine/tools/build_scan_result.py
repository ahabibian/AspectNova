# contracts/tools/build_scan_result.py
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCAN_RESULT_SCHEMA_VERSION = "aspectnova.scan_result.v1"


def utc_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def to_int(v: Any, default: int = 0) -> int:
    try:
        n = int(v)
        return n
    except Exception:
        return default


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def stable_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def normalize_type_hint(type_hint: Any) -> str:
    """
    type_hint might be:
      - str: "pdf" / "application/pdf"
      - dict: {"mime": "application/pdf"} or {"ext": "pdf"} or {"type": "..."}
      - None
    """
    if type_hint is None:
        return ""
    if isinstance(type_hint, str):
        return type_hint
    if isinstance(type_hint, dict):
        # common keys
        for k in ("ext", "extension", "mime", "mimetype", "type", "content_type", "format"):
            v = type_hint.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # fallback: stringify (but keep it short)
        try:
            return json.dumps(type_hint, ensure_ascii=False)
        except Exception:
            return ""
    # fallback
    return str(type_hint)


def guess_ext(type_hint: Any, filename: str = "") -> str:
    """
    Robust ext guessing.
    - If filename has .ext => use it
    - Else use type_hint string/dict (mime or ext)
    """
    # 1) filename wins
    fn = (filename or "").strip()
    if "." in fn and not fn.endswith("."):
        ext = fn.rsplit(".", 1)[-1].lower()
        if 1 <= len(ext) <= 10:
            return ext

    h = normalize_type_hint(type_hint).lower()

    # 2) if type_hint is an ext
    if h in {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "csv", "txt", "json", "xml", "png", "jpg", "jpeg", "gif", "zip"}:
        return h

    # 3) mime mapping
    mime_map = {
        "application/pdf": "pdf",
        "text/plain": "txt",
        "text/csv": "csv",
        "application/json": "json",
        "application/xml": "xml",
        "image/png": "png",
        "image/jpeg": "jpg",
        "application/zip": "zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "application/vnd.ms-powerpoint": "ppt",
    }
    for mime, ext in mime_map.items():
        if mime in h:
            return ext

    # 4) last resort
    return "unknown"


def extract_files(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Tries to locate payload file list in common locations.
    """
    # common candidates
    for key in ("files", "items", "entries"):
        v = payload.get(key)
        if isinstance(v, list):
            return v

    scan = payload.get("scan")
    if isinstance(scan, dict):
        for key in ("files", "items", "entries"):
            v = scan.get(key)
            if isinstance(v, list):
                return v

    # fallback: no files
    return []


def file_size_bytes(item: Dict[str, Any]) -> int:
    for k in ("size_bytes", "bytes", "size", "length"):
        if k in item:
            return to_int(item.get(k), 0)
    return 0


def file_name(item: Dict[str, Any]) -> str:
    for k in ("name", "filename", "file_name", "path"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            # if path, get basename
            return v.split("/")[-1].split("\\")[-1]
    return ""


def file_type_hint(item: Dict[str, Any]) -> Any:
    for k in ("type_hint", "mime", "mimetype", "content_type", "type"):
        if k in item:
            return item.get(k)
    return None


def build_scan_result(payload: Dict[str, Any], source_payload_name: str) -> Dict[str, Any]:
    files = extract_files(payload)

    normalized_files: List[Dict[str, Any]] = []
    total_bytes = 0
    by_ext: Dict[str, int] = {}

    for it in files:
        if not isinstance(it, dict):
            continue
        name = file_name(it)
        th = file_type_hint(it)
        ext = guess_ext(th, filename=name)
        sz = file_size_bytes(it)

        total_bytes += sz
        by_ext[ext] = by_ext.get(ext, 0) + sz

        normalized_files.append(
            {
                "name": name or "unknown",
                "ext": ext,
                "bytes": sz,
                "type_hint": normalize_type_hint(th),
            }
        )

    scan_id = stable_hash(f"{source_payload_name}:{total_bytes}:{len(normalized_files)}")

    scan_result = {
        "schema_version": SCAN_RESULT_SCHEMA_VERSION,
        "meta": {
            "generated_at": utc_iso_z(),
            "source_payload": source_payload_name,
            "scan_id": scan_id,
        },
        "scan": {
            "kpis": {
                "total_bytes": total_bytes,
                "file_count": len(normalized_files),
                "bytes_by_ext": by_ext,
            },
            "files": normalized_files,
        },
    }
    return scan_result


def main() -> int:
    import sys

    if len(sys.argv) != 3:
        print("Usage: python contracts/tools/build_scan_result.py <payload.json> <out_scan_result.json>")
        return 2

    payload_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    if not payload_path.exists():
        print(f"[build_scan_result] Input not found: {payload_path}")
        return 2

    payload = read_json(payload_path)
    if not isinstance(payload, dict):
        print("[build_scan_result] Payload must be a JSON object")
        return 2

    scan_result = build_scan_result(payload, source_payload_name=payload_path.name)
    write_json(out_path, scan_result)
    print(f"[build_scan_result] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
