from __future__ import annotations

import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _norm_rel(path_s: str) -> str:
    s = str(path_s or "").replace("\\", "/").lstrip("./")
    while s.startswith("/"):
        s = s[1:]
    return s


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _infer_epoch_seconds(v: Any) -> float | None:
    """
    Agent scan may emit mtime as:
      - seconds (1e9 range)
      - milliseconds (1e12-1e13 range)
      - nanoseconds (1e18 range)
    """
    try:
        x = float(v)
    except Exception:
        return None

    if x <= 0:
        return None

    if x > 1e17:  # ns
        return x / 1e9
    if x > 1e13:  # us (unlikely)
        return x / 1e6
    if x > 1e11:  # ms
        return x / 1e3
    return x  # seconds


def _to_iso_utc(epoch_seconds: float | None) -> str | None:
    if epoch_seconds is None:
        return None
    try:
        dt = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        return dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    except Exception:
        return None


def _extract_agent_scan(scan_result: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    root = str(scan_result.get("root") or "").strip()
    files = scan_result.get("files") or []
    stats = scan_result.get("stats") or {}

    if not isinstance(files, list):
        files = []
    if not isinstance(stats, dict):
        stats = {}

    return root, files, stats


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "Usage: python contracts/tools/build_scan_payload.py <scan_request.json> <scan_result.json> <eii_result.json> <out_scan_payload.json>",
            file=sys.stderr,
        )
        return 2

    req_path, scan_res_path, eii_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    req = read_json(req_path)
    scan_res = read_json(scan_res_path)
    eii = read_json(eii_path)

    scan_root, files, stats = _extract_agent_scan(scan_res)

    # Summary numbers
    total_files = int(stats.get("total_files") or len(files))
    total_bytes = float(stats.get("total_bytes") or 0.0)
    if total_bytes <= 0 and files:
        total_bytes = float(sum(float((f or {}).get("size") or 0) for f in files))

    # Build items (file-level)
    device_id = (req.get("device") or {}).get("device_id") or "device-unknown"
    items: List[Dict[str, Any]] = []

    for f in files:
        if not isinstance(f, dict):
            continue
        rel = _norm_rel(f.get("rel_path") or f.get("path") or "")
        if not rel:
            continue

        size_bytes = float(f.get("size") or 0.0)
        ext = (Path(rel).suffix or "").lstrip(".").lower()
        base = Path(rel).name

        mtime_s = _infer_epoch_seconds(f.get("mtime"))
        modified_at = _to_iso_utc(mtime_s)

        file_id = _sha256_hex(f"{device_id}|{rel}")
        path_token = f"path://{_sha256_hex(rel)}"
        name_hash = _sha256_hex(base)

        items.append(
            {
                "file_id": file_id,
                "path_token": path_token,
                "name_hash": name_hash,
                "type_hint": {
                    "ext": ext,
                    "mime": None,
                    "category": None,
                },
                "size_bytes": size_bytes,
                "timestamps": {
                    "created_at": None,
                    "modified_at": modified_at,
                    "accessed_at": None,
                },
                "location_class": "UNKNOWN",
                "origin": {"scanner": "agent", "confidence": 0.8},
                "signals": {},
            }
        )

    # Put some raw relative paths into extensions for v2 adapters (safe + limited)
    paths_sample = [(_norm_rel((f or {}).get("rel_path") or (f or {}).get("path") or "")) for f in files[:200]]
    paths_sample = [p for p in paths_sample if p]

    payload: Dict[str, Any] = {
        "schema_id": "aspectnova.scan_payload",
        "schema_version": "aspectnova.scan_payload.v1",
        "meta": {
            "generated_at": _utc_now_iso(),
            "pipeline": "tep.v1",
            "source": {
                "scan_request": str(Path(req_path).name),
                "scan_result": str(Path(scan_res_path).name),
                "eii_result": str(Path(eii_path).name),
            },
        },
        "device": req.get("device") or {"device_id": device_id, "os": None, "storage_type": None},
        "scan": {
            # executor شما روی canonical.root حساب می‌کند
            "canonical": {"root": scan_root},
            "root_scope": {
                "mode": "classified",
                "root_token": f"root://{_sha256_hex(scan_root)}",
            },
            "summary": {
                "files_seen": int(total_files),
                "dirs_seen": 0,
                "errors_count": 0,
                "bytes_scanned": float(total_bytes),
            },
            "items": items,
        },
        "eii": {
            "schema_id": eii.get("schema_id"),
            "schema_version": eii.get("schema_version"),
            "source_scan": eii.get("source_scan") or {},
            "aggregates": eii.get("aggregates") or {},
            "optimization_potential": eii.get("optimization_potential") or {},
        },
        "policy_context": {
            "profile": "default",
            "priority": "medium",
            "path_handling": "classified",
        },
        "extensions": {
            "local_paths_sample": paths_sample,
        },
    }

    write_json(out_path, payload)
    print(f"[build_scan_payload] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
