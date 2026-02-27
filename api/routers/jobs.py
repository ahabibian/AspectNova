from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from api.auth.api_key import require_api_key
from core.engine.job_store import get_job, job_dir

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["jobs"])


def _server_env() -> str:
    return (os.environ.get("ASPECTNOVA_ENV") or "dev").strip().lower()


def _project_root() -> Path:
    """
    Server-side project root.

    - Preferred: ASPECTNOVA_ROOT (absolute path).
    - Dev fallback: current working directory.
    - Production: if ASPECTNOVA_ENV=prod and ASPECTNOVA_ROOT is missing -> 500.
    """
    val = os.environ.get("ASPECTNOVA_ROOT")
    if val:
        return Path(val).resolve()

    if _server_env() == "prod":
        raise HTTPException(status_code=500, detail="Server misconfigured: ASPECTNOVA_ROOT is not set")

    return Path.cwd().resolve()


def _read_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Missing file: {p.name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read {p.name}: {e}")


def _require_job(root: Path, workspace_id: str, run_id: str) -> Dict[str, Any]:
    job = get_job(root=root, workspace_id=workspace_id, run_id=run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _job_folder(root: Path, workspace_id: str, run_id: str) -> Path:
    return job_dir(root, workspace_id) / run_id


@router.get(
    "/jobs",
    dependencies=[Depends(require_api_key)],
)
def list_jobs(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = None,
):
    root_p = _project_root()
    base = job_dir(root_p, workspace_id)
    if not base.exists():
        return {"schema_version": "v1", "count": 0, "next_cursor": None, "items": []}

    run_dirs = sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    if cursor:
        run_dirs = [p for p in run_dirs if p.name < cursor]

    items: List[Dict[str, Any]] = []
    for d in run_dirs[:limit]:
        meta_path = d / "job_meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path)
            items.append(
                {
                    "job_id": meta.get("job_id", d.name),
                    "workspace_id": meta.get("workspace_id", workspace_id),
                    "status": meta.get("status"),
                    "created_at": meta.get("created_at"),
                    "finished_at": meta.get("finished_at"),
                }
            )
        else:
            job = get_job(root=root_p, workspace_id=workspace_id, run_id=d.name) or {}
            items.append(
                {
                    "job_id": d.name,
                    "workspace_id": workspace_id,
                    "status": job.get("status", "unknown"),
                    "created_at": job.get("created_at"),
                    "finished_at": job.get("finished_at"),
                }
            )

    next_cursor = items[-1]["job_id"] if len(items) == limit else None
    return {"schema_version": "v1", "count": len(items), "next_cursor": next_cursor, "items": items}


@router.get(
    "/jobs/{run_id}",
    dependencies=[Depends(require_api_key)],
)
def get_job_status(
    workspace_id: str,
    run_id: str,
):
    root_p = _project_root()
    job = _require_job(root_p, workspace_id, run_id)
    return job


@router.get(
    "/jobs/{run_id}/report",
    dependencies=[Depends(require_api_key)],
)
def get_job_report(
    workspace_id: str,
    run_id: str,
):
    root_p = _project_root()
    _require_job(root_p, workspace_id, run_id)
    d = _job_folder(root_p, workspace_id, run_id)

    report_path = d / "execution_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=409, detail="Report not ready")

    return _read_json(report_path)


@router.get(
    "/jobs/{run_id}/logs",
    dependencies=[Depends(require_api_key)],
)
def get_job_logs(
    workspace_id: str,
    run_id: str,
    tail: int = Query(0, ge=0, le=5000),
):
    root_p = _project_root()
    _require_job(root_p, workspace_id, run_id)
    d = _job_folder(root_p, workspace_id, run_id)

    log_path = d / "job.log.jsonl"
    if log_path.exists():
        if tail > 0:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            lines = lines[-tail:]
            return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""))
        return PlainTextResponse(log_path.read_text(encoding="utf-8"))

    report_path = d / "execution_report.json"
    if report_path.exists():
        report = _read_json(report_path)
        summary = report.get("summary") or {}
        runner = report.get("runner") or {}
        fallback_lines = [
            f'{{"level":"INFO","stage":"report","message":"Execution report available","run_id":"{run_id}"}}',
            f'{{"level":"INFO","stage":"report","message":"execute_requested={runner.get("execute_requested")}","run_id":"{run_id}"}}',
            f'{{"level":"INFO","stage":"report","message":"attempted_archive={summary.get("attempted_archive")}","run_id":"{run_id}"}}',
            f'{{"level":"INFO","stage":"report","message":"errors={summary.get("errors")}","run_id":"{run_id}"}}',
        ]
        return PlainTextResponse("\n".join(fallback_lines) + "\n")

    raise HTTPException(status_code=404, detail="Log file not found")


def _find_payload_zip_from_report(d: Path) -> Optional[Path]:
    report_path = d / "execution_report.json"
    if not report_path.exists():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    archive_info = report.get("archive") or {}
    zip_path = archive_info.get("zip_path")
    if not zip_path:
        return None
    z = Path(zip_path)
    return z if z.exists() else None


def _find_payload_zip_from_archive_root(root_p: Path, workspace_id: str, run_id: str) -> Optional[Path]:
    """
    Fallback to the canonical archive layout:
      {root}/.aspectnova/archive/{workspace_id}/{run_id}/payload.zip
    """
    z = root_p / ".aspectnova" / "archive" / workspace_id / run_id / "payload.zip"
    return z if z.exists() else None


@router.get(
    "/jobs/{run_id}/artifact",
    dependencies=[Depends(require_api_key)],
)
def get_job_artifact(
    workspace_id: str,
    run_id: str,
):
    root_p = _project_root()
    _require_job(root_p, workspace_id, run_id)
    d = _job_folder(root_p, workspace_id, run_id)

    # 1) contracts/.../{run_id}/payload.zip
    local_zip = d / "payload.zip"
    if local_zip.exists():
        return FileResponse(path=str(local_zip), filename=f"{run_id}.payload.zip", media_type="application/zip")

    # 2) execution_report.json -> archive.zip_path
    z = _find_payload_zip_from_report(d)
    if z:
        return FileResponse(path=str(z), filename=f"{run_id}.payload.zip", media_type="application/zip")

    # 3) canonical archive location fallback
    z2 = _find_payload_zip_from_archive_root(root_p, workspace_id, run_id)
    if z2:
        return FileResponse(path=str(z2), filename=f"{run_id}.payload.zip", media_type="application/zip")

    # Artifact is not ready yet (job likely queued/running or no archive produced)
    raise HTTPException(status_code=409, detail="Artifact not ready")
