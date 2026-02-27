from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.engine.job_store import job_dir


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def meta_path(root: Path, workspace_id: str, run_id: str) -> Path:
    return job_dir(root, workspace_id) / run_id / "job_meta.json"


def read_meta(root: Path, workspace_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    p = meta_path(root, workspace_id, run_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_meta(root: Path, workspace_id: str, run_id: str, data: Dict[str, Any]) -> None:
    p = meta_path(root, workspace_id, run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_meta(
    *,
    root: Path,
    workspace_id: str,
    run_id: str,
    status: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    artifacts: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    existing = read_meta(root, workspace_id, run_id) or {}
    now = utc_now_iso()

    meta: Dict[str, Any] = {
        "schema_version": "v1",
        "job_id": existing.get("job_id", run_id),
        "workspace_id": existing.get("workspace_id", workspace_id),
        "status": existing.get("status", "queued"),
        "created_at": existing.get("created_at", now),
        "started_at": existing.get("started_at"),
        "finished_at": existing.get("finished_at"),
        "artifacts": existing.get("artifacts", {}),
    }

    if status is not None:
        meta["status"] = status
    if started_at is not None:
        meta["started_at"] = started_at
    if finished_at is not None:
        meta["finished_at"] = finished_at
    if artifacts:
        meta["artifacts"] = {**meta.get("artifacts", {}), **artifacts}

    write_meta(root, workspace_id, run_id, meta)
    return meta
