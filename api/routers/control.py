# api/routers/control.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth.api_key import require_api_key
from core.engine.job_logger import append_log
from core.engine.job_meta import upsert_meta
from core.engine.job_store import get_job, ref as job_ref, update_job
from core.engine.runner import execute_job
from core.storage.paths import WorkspacePaths


router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["control"])


def _require_root_env() -> Path:
    root = os.environ.get("ASPECTNOVA_ROOT")
    if not root:
        raise HTTPException(status_code=500, detail="Server misconfigured: ASPECTNOVA_ROOT is not set")
    return Path(root).resolve()


def _env_mode() -> str:
    return (os.environ.get("ASPECTNOVA_ENV") or "dev").strip().lower()


def _expected_approval_secret() -> Optional[str]:
    return os.environ.get("ASPECTNOVA_APPROVAL_SECRET")


class ApproveBody(BaseModel):
    confirm_secret: str


class ExecuteBody(BaseModel):
    scan_path: str
    rules_path: str
    safe_mode: bool = False
    execute: bool = True
    remove_original: bool = True
    confirm_secret: Optional[str] = None


@router.post("/jobs/{run_id}/approve", dependencies=[Depends(require_api_key)])
def approve_job(workspace_id: str, run_id: str, body: ApproveBody) -> Dict[str, Any]:
    root = _require_root_env()
    mode = _env_mode()

    expected = _expected_approval_secret()
    if expected and body.confirm_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid approval secret")

    paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)
    if not paths.contracts_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    approval = {
        "schema_version": "v1",
        "workspace_id": workspace_id,
        "run_id": run_id,
        "approved": True,
        "approved_at": upsert_meta.__globals__["utc_now_iso"](),
        "mode": mode,
    }
    lock = {
        "schema_version": "v1",
        "workspace_id": workspace_id,
        "run_id": run_id,
        "state": "approved",
        "updated_at": upsert_meta.__globals__["utc_now_iso"](),
    }

    (paths.contracts_dir / "approval.json").write_text(__import__("json").dumps(approval, indent=2), encoding="utf-8")
    (paths.contracts_dir / "run.lock.json").write_text(__import__("json").dumps(lock, indent=2), encoding="utf-8")

    append_log(
        root=root,
        workspace_id=workspace_id,
        run_id=run_id,
        level="INFO",
        stage="control",
        event="approved",
        message="Run approved",
        meta={},
    )

    return {"status": "approved", "approval": approval}


@router.post("/jobs/{run_id}/execute", dependencies=[Depends(require_api_key)])
def execute_job_api(workspace_id: str, run_id: str, body: ExecuteBody) -> Dict[str, Any]:
    root = _require_root_env()
    mode = _env_mode()

    paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)
    if not paths.contracts_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    approval_path = paths.contracts_dir / "approval.json"
    lock_path = paths.contracts_dir / "run.lock.json"
    if not approval_path.exists() or not lock_path.exists():
        raise HTTPException(status_code=403, detail="Run not approved")

    jref = job_ref(root, workspace_id, run_id)
    job = get_job(root=root, workspace_id=workspace_id, run_id=run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Run not found")

    append_log(
        root=root,
        workspace_id=workspace_id,
        run_id=run_id,
        level="INFO",
        stage="control",
        event="execute_started",
        message="Pipeline started",
        meta={
            "scan_path": body.scan_path,
            "rules_path": body.rules_path,
            "safe_mode": body.safe_mode,
            "execute": body.execute,
            "remove_original": body.remove_original,
        },
    )

    req: Dict[str, Any] = dict(job.get("request") or {})
    req["root"] = str(root)
    req["scan_path"] = body.scan_path
    req["rules_path"] = body.rules_path
    req["safe_mode"] = bool(body.safe_mode)
    req["execute"] = bool(body.execute)
    req["remove_original"] = bool(body.remove_original)

    if body.confirm_secret is not None:
        req["confirm_secret"] = body.confirm_secret
    else:
        req["confirm_secret"] = "" if mode == "dev" else None

    try:
        execute_job(jref, req)
    except Exception as e:
        update_job(jref, status="failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    append_log(
        root=root,
        workspace_id=workspace_id,
        run_id=run_id,
        level="INFO",
        stage="control",
        event="execute_completed",
        message="Pipeline completed",
        meta={},
    )

    return {"status": "completed", "workspace_id": workspace_id, "run_id": run_id}
