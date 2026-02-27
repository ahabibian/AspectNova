from __future__ import annotations
from pathlib import Path
import sys, json
from datetime import datetime, timezone
import argparse

SCHEMA_ID = "aspectnova.scan.canonical.v1"

def resolve_run_id() -> str | None:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--run-id")
    args, rest = ap.parse_known_args()
    if args.run_id:
        return args.run_id
    if len(rest) >= 1:
        return rest[0]
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("-"):
        return sys.argv[1]
    return None

def main() -> int:
    run_id = resolve_run_id()
    if not run_id:
        print("usage: python .\\run_scan_normalizer.py <run_id> OR --run-id <run_id>")
        return 2

    root = Path("runs") / run_id
    out_dir = root / "output"
    in_dir = root / "input"
    evidence_dir = out_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    in_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        in_dir / "scan_result.canonical.json",
        in_dir / "scan_result.json",
        out_dir / "scan_result.canonical.json",
        out_dir / "scan_result.canonical.v1.json",
    ]
    scan_in = next((p for p in candidates if p.exists()), None)
    if scan_in is None:
        print(json.dumps({
            "status": "FAIL",
            "where": "scan_normalizer",
            "reason": "missing_scan_input",
            "expected_any_of": [str(p) for p in candidates],
        }, indent=2))
        return 1

    data = json.loads(scan_in.read_text(encoding="utf-8", errors="strict"))
    items = data.get("items") or data.get("files") or []
    if not isinstance(items, list) or len(items) == 0:
        print(json.dumps({"status":"FAIL","where":"scan_normalizer","reason":"invalid_scan_shape","input":str(scan_in)}, indent=2))
        return 1

    now = datetime.now(timezone.utc).isoformat()

    out_items = []
    for it in items:
        if not isinstance(it, dict):
            continue
        path = it.get("path") or it.get("full_path") or it.get("name")
        if not path:
            continue
        out_items.append({
            "path": str(path),
            "size": it.get("size"),
            "mtime_utc": it.get("mtime_utc") or it.get("mtime") or it.get("modified_utc")
        })

    if not out_items:
        print(json.dumps({"status":"FAIL","where":"scan_normalizer","reason":"no_valid_items","input":str(scan_in)}, indent=2))
        return 1

    canonical = {
        "schema_id": SCHEMA_ID,
        "schema_version": "scan_canonical/1.0",
        "run_id": run_id,
        "generated_at_utc": now,
        "items": out_items,
        "counts": {
            "items_in": len(items),
            "items_out": len(out_items)
        }
    }

    payload = json.dumps(canonical, ensure_ascii=False, indent=2) + "\n"

    out_a = out_dir / "scan_result.canonical.json"
    out_b = out_dir / "scan_result.canonical.v1.json"
    out_a.write_text(payload, encoding="utf-8")
    out_b.write_text(payload, encoding="utf-8")

    (evidence_dir / "_tmp_scan_normalizer.log").write_text(
        json.dumps({"status":"OK","input_used":str(scan_in),"written":[str(out_a),str(out_b)],"counts":canonical["counts"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("SCAN_NORMALIZER DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())