# api/models/run_models.py
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any

RunMode = Literal["safe", "full"]
RunStatus = Literal["created", "running", "succeeded", "failed"]

class CreateRunRequest(BaseModel):
    root: str = Field(..., description="Absolute path to repo/workspace root on server")
    scan_path: str
    rules_path: str
    mode: RunMode = "safe"
    execute: bool = False
    safe_mode: bool = True

class CreateRunResponse(BaseModel):
    workspace_id: str
    run_id: str
    status: RunStatus

class RunStatusResponse(BaseModel):
    workspace_id: str
    run_id: str
    status: RunStatus
    detail: Optional[str] = None
    artifacts: Dict[str, Any] = Field(default_factory=dict)
