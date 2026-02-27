from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.engine.job_store import job_dir


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_log(
    *,
    root: Path,
    workspace_id: str,
    run_id: str,
    level: str,
    stage: str,
    event: str,
    message: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    d = job_dir(root, workspace_id) / run_id
    d.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": _utc_iso(),
        "level": level.upper(),
        "stage": stage,
        "event": event,
        "message": message,
        "meta": meta or {},
    }

    log_path = d / "job.log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
