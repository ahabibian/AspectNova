from __future__ import annotations
import json
import sys
from pathlib import Path
import hashlib

JUNK_EXT = {".tmp", ".bak", ".old"}
LARGE_MIN = 10 * 1024 * 1024   # 10MB
DUP_HASH_MAX = 5 * 1024 * 1024 # hash only up to 5MB

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main(run_id: str) -> int:
    base = Path("runs") / run_id / "output"
    canon_p = base / "scan_result.canonical.v1.json"
    verdict_p = base / "evidence" / "verdict.json"

    if not canon_p.exists():
        print(f"ERROR: missing canonical scan: {canon_p}")
        return 2
    if not verdict_p.exists():
        print(f"ERROR: missing verdict: {verdict_p}")
        return 3

    canon = json.loads(canon_p.read_text(encoding="utf-8"))
    items = canon.get("items") or canon.get("files") or []

    verdict = json.loads(verdict_p.read_text(encoding="utf-8"))
    findings = verdict.get("findings")
    if not isinstance(findings, list):
        findings = []
        verdict["findings"] = findings

    # 1) junk extensions + 2) large files
    for it in items:
        p = str(it.get("path") or "")
        if not p:
            continue
        sz = int(it.get("size") or 0)
        ext = Path(p).suffix.lower()

        if ext in JUNK_EXT:
            findings.append({
                "code": "JUNK_EXTENSION",
                "severity": "LOW",
                "path": p,
                "detail": {"ext": ext, "size": sz}
            })
        if sz >= LARGE_MIN:
            findings.append({
                "code": "LARGE_FILE",
                "severity": "MEDIUM",
                "path": p,
                "detail": {"size": sz, "min_bytes": LARGE_MIN}
            })

    # 3) duplicate content (safe hashing)
    by_hash: dict[str, list[str]] = {}
    for it in items:
        p = Path(str(it.get("path") or ""))
        if not p or not p.exists():
            continue
        sz = int(it.get("size") or 0)
        if sz <= 0 or sz > DUP_HASH_MAX:
            continue
        try:
            hx = sha256_file(p)
            by_hash.setdefault(hx, []).append(str(p))
        except Exception:
            continue

    for hx, paths in by_hash.items():
        if len(paths) >= 2:
            findings.append({
                "code": "DUPLICATE_CONTENT",
                "severity": "MEDIUM",
                "paths": paths,
                "detail": {"sha256": hx, "count": len(paths)}
            })

    # summary (non-breaking)
    sm = verdict.get("summary")
    if not isinstance(sm, dict):
        sm = {}
    totals = sm.get("totals")
    if not isinstance(totals, dict):
        totals = {}
    totals["findings"] = len(findings)
    sm["totals"] = totals
    verdict["summary"] = sm

    verdict_p.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: verdict updated. findings={len(findings)} -> {verdict_p}")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python tools/dev/verdict_postprocess_v1.py <run_id>")
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
