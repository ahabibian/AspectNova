from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .normalize import canonicalize_output


@dataclass(frozen=True)
class ScanEntry:
    path: str          # relative to root
    size: int
    mtime_ns: int
    sha256: Optional[str] = None


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _should_skip_dir(dirname: str, exclude_dirs: List[str]) -> bool:
    name = dirname.lower()
    return any(name == d.lower() for d in exclude_dirs)


def _ext_allowed(path: Path, include_exts: List[str]) -> bool:
    if not include_exts:
        return True
    ext = path.suffix.lower().lstrip(".")
    include = [e.lower().lstrip(".") for e in include_exts]
    return ext in include


def _hash_file(path: Path, max_bytes: int) -> str:
    if max_bytes <= 0:
        raise ValueError("hash_max_bytes must be > 0 to hash")
    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = max_bytes
        while remaining > 0:
            chunk = f.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def scan_directory(
    root: Union[str, Path],
    *,
    exclude_dirs: Optional[List[str]] = None,
    include_extensions: Optional[List[str]] = None,
    hash_max_bytes: int = 0,
) -> Dict[str, Any]:
    """
    Scan a directory (or a file) and return internal scan object.
    """
    root = Path(root).resolve()
    exclude_dirs = exclude_dirs or ["node_modules", ".git", ".venv", "__pycache__"]
    include_extensions = include_extensions or []

    entries: List[ScanEntry] = []

    if root.is_file():
        rel = root.name
        st = root.stat()
        sha = _hash_file(root, hash_max_bytes) if hash_max_bytes > 0 else None
        entries.append(ScanEntry(path=rel, size=int(st.st_size), mtime_ns=int(st.st_mtime_ns), sha256=sha))
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d, exclude_dirs)]
            base = Path(dirpath)

            for fn in filenames:
                p = base / fn
                if not _ext_allowed(p, include_extensions):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue

                rel = str(p.relative_to(root))
                sha = None
                if hash_max_bytes > 0:
                    try:
                        sha = _hash_file(p, hash_max_bytes)
                    except Exception:
                        sha = None

                entries.append(
                    ScanEntry(
                        path=rel,
                        size=int(st.st_size),
                        mtime_ns=int(st.st_mtime_ns),
                        sha256=sha,
                    )
                )

    return {
        "root": str(root),
        "entries": entries,
        "hash_max_bytes": int(hash_max_bytes),
    }


def build_raw_payload(*args, **kwargs) -> Dict[str, Any]:
    """
    Supports both call styles used in tests/legacy code:

      1) build_raw_payload(cfg, root=Path(...))
      2) build_raw_payload(scan_obj)
    """
    # Style (1): build_raw_payload(cfg, root=...)
    if args and isinstance(args[0], dict) and "scan" in args[0] and "output" in args[0] and "root" in kwargs:
        cfg = args[0]
        root = kwargs["root"]
        exclude_dirs = list(cfg.get("scan", {}).get("exclude_dirs", ["node_modules", ".git", ".venv", "__pycache__"]))
        include_exts = list(cfg.get("scan", {}).get("include_extensions", []))
        hash_max_bytes = int(cfg.get("scan", {}).get("hash_max_bytes", 0))

        scan_obj = scan_directory(
            root,
            exclude_dirs=exclude_dirs,
            include_extensions=include_exts,
            hash_max_bytes=hash_max_bytes,
        )
        return build_raw_payload(scan_obj)

    # Style (2): build_raw_payload(scan_obj)
    scan: Dict[str, Any] = args[0] if args else kwargs["scan"]
    entries: List[ScanEntry] = scan["entries"]

    files: List[Dict[str, Any]] = []
    total_files = 0
    total_bytes = 0

    for e in entries:
        total_files += 1
        total_bytes += int(e.size)

        d: Dict[str, Any] = {
            "path": e.path,
            "size": int(e.size),
            "mtime": int(e.mtime_ns),  # schema expects integer "mtime"
        }
        # IMPORTANT: only include sha256 when we actually computed it
        if e.sha256 is not None:
            d["sha256"] = e.sha256

        files.append(d)

    return {
        "schema_id": "scan-result",
        "schema_version": "v1",
        "generated_at": _utc_now_iso_z(),
        "root": scan.get("root") or "",
        "stats": {
            "total_files": total_files,
            "total_bytes": total_bytes,
        },
        "files": files,
    }


def build_canonical_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    return canonicalize_output(raw)


def scan_and_write_outputs(cfg, *, override_root=None, root_override=None):
    """
    Backward-compat API: tests import this from agent.scanner.
    Actual implementation lives in agent.cli.
    """
    from .cli import scan_and_write_outputs as _impl
    return _impl(cfg, override_root=override_root, root_override=root_override)
