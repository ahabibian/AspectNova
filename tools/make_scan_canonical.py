import json
import os
from pathlib import Path
from datetime import datetime, timezone

EXCLUDE_DIRS = {".git", ".aspectnova", "node_modules"}

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def main():
    root = Path(".").resolve()

    files = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue

        rel = p.relative_to(root).as_posix()

        # exclude big/system dirs
        if rel.split("/")[0] in EXCLUDE_DIRS:
            continue

        # keep .venv in scan (important for tests), but you can exclude later if you want
        st = p.stat()
        files.append({
            "rel_path": rel,
            "size_bytes": st.st_size,
        })

    out = {
        "schema_id": "scan-result-canonical",
        "schema_version": "v1.1",
        "generated_at": utc_now(),
        "root": str(root),
        "files": files,
    }

    out_path = root / "shared" / "scan_result.canonical.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] wrote {out_path} | files={len(files)}")

if __name__ == "__main__":
    main()
