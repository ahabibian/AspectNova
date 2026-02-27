from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--include-hidden", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    files = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue

        rel = p.relative_to(root).as_posix()

        if not args.include_hidden:
            first = rel.split("/", 1)[0]
            if first.startswith("."):
                continue

        try:
            st = p.stat()
        except OSError:
            continue

        files.append(
            {
                "rel_path": rel,
                "size_bytes": int(st.st_size),
                "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )

    payload = {
        "schema_id": "scan-result",
        "schema_version": "v1.1",
        "generated_at": utc_now(),
        "root": str(root),
        "files": files,
    }

    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {out} | files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
