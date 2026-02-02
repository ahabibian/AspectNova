import json
from pathlib import Path
from datetime import datetime


def adapt_scan_to_items(scan_path: Path, out_path: Path):
    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    files = scan.get("files", [])
    items = []

    for idx, f in enumerate(files):
        path = f.get("path")
        if not path:
            continue

        is_dir = str(path).endswith("/")
        p = Path(str(path).rstrip("/"))

        items.append({
            "id": f"item-{idx}",
            "path": str(path).rstrip("/"),
            "basename": p.name,
            "ext": p.suffix.lstrip("."),
            "is_file": not is_dir,
            "is_dir": is_dir,
            "size_bytes": f.get("size", 0),
            "mtime_utc": datetime.utcfromtimestamp(
                ((f.get("mtime", 0) or 0) / 1e9)
            ).isoformat() + "Z",
        })

    scan["items"] = items
    scan["items_count"] = len(items)

    out_path.write_text(
        json.dumps(scan, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"[OK] adapted scan -> items: {len(items)}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    adapt_scan_to_items(Path(args.scan), Path(args.out))
