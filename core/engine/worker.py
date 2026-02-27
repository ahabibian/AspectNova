from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.engine.job_store import (
    claim_next_queued_job,
    get_job,
    ref as job_ref,
    update_job,
)
from core.engine.job_logger import append_log
from core.engine.job_meta import upsert_meta
from core.engine.runner import run_pipeline_for_job


def process_one_job(
    *,
    root: Path,
    workspace_id: str,
    safe_mode: bool,
    execute: bool,
    remove_original: bool,
) -> Optional[Dict[str, Any]]:
    """
    Claims and processes at most one queued job.
    Returns the job dict if a job was processed, otherwise None.
    """
    job = claim_next_queued_job(root=root, workspace_id=workspace_id)
    if not job:
        return None

    run_id = job["run_id"]
    jref = job_ref(root, workspace_id, run_id)

    update_job(jref, status="running", error=None)
    upsert_meta(root=root, workspace_id=workspace_id, run_id=run_id, status="running", started_at=upsert_meta.__globals__["utc_now_iso"]())  # avoids duplicate import

    append_log(
        root=root,
        workspace_id=workspace_id,
        run_id=run_id,
        level="INFO",
        stage="worker",
        event="job_started",
        message="Job started",
        meta={"safe_mode": safe_mode, "execute": execute, "remove_original": remove_original},
    )

    try:
        # Run the actual pipeline for this job
        artifacts = run_pipeline_for_job(
            root=root,
            workspace_id=workspace_id,
            run_id=run_id,
            safe_mode=safe_mode,
            execute=execute,
            remove_original=remove_original,
        )

        update_job(jref, status="completed", error=None, artifacts=artifacts or {})
        upsert_meta(
            root=root,
            workspace_id=workspace_id,
            run_id=run_id,
            status="completed",
            finished_at=upsert_meta.__globals__["utc_now_iso"](),
            artifacts=artifacts or {},
        )

        append_log(
            root=root,
            workspace_id=workspace_id,
            run_id=run_id,
            level="INFO",
            stage="worker",
            event="job_completed",
            message="Job completed",
            meta={"artifacts": artifacts or {}},
        )
        return get_job(root=root, workspace_id=workspace_id, run_id=run_id)

    except Exception as e:
        update_job(jref, status="failed", error=str(e))
        upsert_meta(
            root=root,
            workspace_id=workspace_id,
            run_id=run_id,
            status="failed",
            finished_at=upsert_meta.__globals__["utc_now_iso"](),
        )

        append_log(
            root=root,
            workspace_id=workspace_id,
            run_id=run_id,
            level="ERROR",
            stage="worker",
            event="job_failed",
            message="Job failed",
            meta={"error": str(e)},
        )
        raise


def worker_loop(root: Path, workspace_id: str = "ws_api", poll_seconds: float = 1.0) -> None:
    """
    Development worker loop: continuously processes queued jobs.
    """
    root = Path(root).resolve()
    while True:
        processed = process_one_job(
            root=root,
            workspace_id=workspace_id,
            safe_mode=True,
            execute=False,
            remove_original=False,
        )
        if not processed:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    worker_loop(Path(".").resolve())
