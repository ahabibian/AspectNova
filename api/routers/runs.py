from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth.api_key import require_api_key
from api.models.runs import CreateRunRequest, CreateRunResponse, RunStatusResponse
from core.engine.job_store import get_job, init_job, ref as job_ref, update_job

from core.engine.job_logger import append_log
from core.engine.job_meta import upsert_meta

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["runs"])


def _root_path(root: str) -> Path:
    return Path(root).resolve()


def _job_to_status(job: Dict[str, Any]) -> RunStatusResponse:
    return RunStatusResponse(
        workspace_id=job["workspace_id"],
        run_id=job["run_id"],
        status=job.get("status", "unknown"),
        detail=job.get("error"),
        artifacts=job.get("artifacts") or {},
    )


@router.post(
    "/runs",
    response_model=CreateRunResponse,
    dependencies=[Depends(require_api_key)],
)
def create_run(workspace_id: str, req: CreateRunRequest) -> CreateRunResponse:
    root = _root_path(req.root)
    run_id = time.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:10]

    # 1) Initialize job record in the job store
    init_job(
        root=root,
        workspace_id=workspace_id,
        run_id=run_id,
        request=req.model_dump(),
    )

    # 2) Canonical status (aligns with: queued -> running -> completed|failed|cancelled)
    update_job(
        job_ref(root, workspace_id, run_id),
        status="queued",
        error=None,
        artifacts={},
    )

    # 3) Canonical job metadata file (enterprise-friendly)
    upsert_meta(
        root=root,
        workspace_id=workspace_id,
        run_id=run_id,
        status="queued",
        artifacts={
            "report": "execution_report.json",
            "logs": "job.log.jsonl",
            "payload_zip": "payload.zip",
        },
    )

    # 4) Structured JSONL log line
    append_log(
        root=root,
        workspace_id=workspace_id,
        run_id=run_id,
        level="INFO",
        stage="api",
        event="run_created",
        message="Run created",
        meta={
            "root": str(root),
            "scan_path": str(getattr(req, "scan_path", "")),
            "rules_path": str(getattr(req, "rules_path", "")),
        },
    )

    return CreateRunResponse(workspace_id=workspace_id, run_id=run_id, status="queued")


@router.get(
    "/runs/{run_id}",
    response_model=RunStatusResponse,
    dependencies=[Depends(require_api_key)],
)
def get_run(
    workspace_id: str,
    run_id: str,
    root: str = Query(..., description="Absolute project root path."),
) -> RunStatusResponse:
    root_p = _root_path(root)
    job = get_job(root=root_p, workspace_id=workspace_id, run_id=run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Run not found")
    return _job_to_status(job)
