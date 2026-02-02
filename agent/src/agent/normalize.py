from __future__ import annotations

from typing import Any, Dict, List


def _to_posix_path(p: str) -> str:
    return p.replace("\\", "/")


def canonicalize_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonicalize output WITHOUT changing schema shape.
    Allowed operations only:
      - normalize path separators
      - sort files deterministically
    """
    out = dict(payload)

    files: List[Dict[str, Any]] = [
        dict(f) for f in out.get("files", []) if isinstance(f, dict)
    ]

    # normalize paths
    for f in files:
        if "path" in f and isinstance(f["path"], str):
            f["path"] = _to_posix_path(f["path"])

    # deterministic ordering
    files.sort(
        key=lambda x: (
            x.get("path", ""),
            int(x.get("size", 0)),
            int(x.get("mtime", 0)),
        )
    )

    out["files"] = files

    # IMPORTANT:
    # - do NOT add/remove root-level fields
    # - do NOT touch stats except keep as-is
    # - do NOT add 'canonical' flag

    return out
