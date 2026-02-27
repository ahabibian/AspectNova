import json
from datetime import datetime, timezone
from pathlib import Path

def _looks_abs(p: str) -> bool:
    if not p:
        return False
    # Windows abs (C:\) or UNC (\\server\share)
    return (len(p) > 2 and p[1] == ":" and (p[2] == "\\" or p[2] == "/")) or p.startswith("\\\\")

def _to_posixish(p: str) -> str:
    return p.replace("\\", "/").lstrip("/")

def normalize(scan_path: Path, out_path: Path):
    d = json.loads(scan_path.read_text(encoding="utf-8"))

    root = d.get("root") or ""
    files = d.get("files") or []
    if not isinstance(files, list) or len(files) == 0:
        raise ValueError("scan has no files[]")

    root_abs = root
    if root_abs.endswith("\\") or root_abs.endswith("/"):
        root_abs = root_abs[:-1]

    items = []
    dropped = 0

    for f in files:
        rel = f.get("path") or f.get("path_rel") or ""
        if not rel:
            dropped += 1
            continue

        rel_norm = _to_posixish(rel)

        if _looks_abs(rel):
            abs_path = rel.replace("/", "\\")
            rel_out = rel_norm
        else:
            abs_path = str(Path(root_abs) / Path(rel_norm))
            abs_path = abs_path.replace("/", "\\")
            rel_out = rel_norm

        size = f.get("size")
        mtime = f.get("mtime")

        items.append({
            "path_rel": rel_out,
            "path_abs": abs_path,
            "size_bytes": int(size) if size is not None else None,
            "mtime_raw": mtime
        })

    out = {
        "schema_id": "aspectnova.scan.canonical.v1",
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "input_schema_id": d.get("schema_id"),
            "input_schema_version": d.get("schema_version"),
            "input_file": str(scan_path)
        },
        "root_abs": root_abs,
        "counts": {
            "files_in": len(files),
            "items_out": len(items),
            "dropped": dropped
        },
        "items": items,
        "files": files
    }

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out["counts"]
