from __future__ import annotations

import json, os, shutil, hashlib, zipfile
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def sha256_file(p: Path, chunk=1024 * 1024) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def is_within_root(root: Path, p: Path) -> bool:
    root = root.resolve()
    try:
        p.resolve().relative_to(root)
        return True
    except Exception:
        return False

@dataclass
class ArchiveResult:
    status: str           # "archived" | "skipped" | "failed"
    rel_path: str
    src_abs: str
    zip_path: str | None
    sha256: str | None
    size_bytes: int | None
    freed_bytes: int
    error: str | None

def archive_files(
    *,
    root: Path,
    archive_base: Path,
    workspace_id: str,
    run_id: str,
    rel_paths: list[str],
    remove_original: bool = True,
) -> tuple[Path, Path, list[ArchiveResult], dict]:
    root = root.resolve()
    archive_dir = (archive_base / workspace_id / run_id).resolve()
    staging_dir = (archive_base.parent / ".staging" / workspace_id / run_id).resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    zip_path = archive_dir / "payload.zip"
    manifest_path = archive_dir / "manifest.json"

    results: list[ArchiveResult] = []
    manifest_items = []

    # 1) stage
    staged_files: list[tuple[Path, str, str, int]] = []  # (staged_abs, rel, sha, size)
    for rel in rel_paths:
        src = (root / rel).resolve()
        if not is_within_root(root, src):
            results.append(ArchiveResult("failed", rel, str(src), None, None, None, 0, "path_outside_root"))
            continue
        if not src.exists() or not src.is_file():
            results.append(ArchiveResult("skipped", rel, str(src), None, None, None, 0, "missing_or_not_file"))
            continue

        sha = sha256_file(src)
        size = src.stat().st_size

        staged = (staging_dir / rel).resolve()
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, staged)
        staged_files.append((staged, rel, sha, size))

    # 2) zip
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for staged, rel, sha, size in staged_files:
            z.write(staged, arcname=rel)

            manifest_items.append({
                "rel_path": rel,
                "sha256": sha,
                "size_bytes": size,
                "archived_at": utc_now_iso(),
            })

    # 3) remove originals (only after zip exists)
    freed_total = 0
    for staged, rel, sha, size in staged_files:
        src = (root / rel).resolve()
        freed = 0
        err = None
        if remove_original:
            try:
                os.remove(src)
                freed = size
            except Exception as e:
                err = f"remove_failed: {e!r}"

        freed_total += freed
        results.append(ArchiveResult(
            "archived" if err is None else "failed",
            rel, str(src), str(zip_path), sha, size, freed, err
        ))

    # 4) manifest
    manifest = {
        "schema_id": "archive-manifest",
        "schema_version": "v1",
        "generated_at": utc_now_iso(),
        "root": str(root),
        "workspace_id": workspace_id,
        "run_id": run_id,
        "zip_path": str(zip_path),
        "items": manifest_items,
        "totals": {
            "items": len(manifest_items),
            "freed_bytes": freed_total,
        }
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # cleanup staging
    shutil.rmtree(staging_dir, ignore_errors=True)

    return zip_path, manifest_path, results, manifest
