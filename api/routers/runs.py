# api/routers/runs.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path

from api.auth.api_key import require_api_key
from api.models.run_models import CreateRunRequest, CreateRunResponse, RunStatusResponse
from api.state.run_registry import RunRegistry

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["runs"])

def _registry(root: str) -> RunRegistry:
    return RunRegistry(root=Path(root).resolve())

@router.post("/runs", response_model=CreateRunResponse, dependencies=[Depends(require_api_key)])
def create_run(workspace_id: str, req: CreateRunRequest):
    reg = _registry(req.root)
    rec = reg.create(workspace_id=workspace_id, request=req.model_dump())
    return CreateRunResponse(workspace_id=workspace_id, run_id=rec.run_id, status=rec.status)

@router.get("/runs/{run_id}", response_model=RunStatusResponse, dependencies=[Depends(require_api_key)])
def get_run(workspace_id: str, run_id: str, root: str):
    reg = _registry(root)
    try:
        rec = reg.load(workspace_id, run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="run not found")
    return RunStatusResponse(
        workspace_id=workspace_id,
        run_id=run_id,
        status=rec.status,
        detail=rec.detail,
        artifacts=rec.artifacts or {},
    )
