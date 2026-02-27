from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    root: str = Field(..., description="Absolute project root path.")
    scan_path: str
    rules_path: str
    mode: str = Field("safe", description="safe|full")
    execute: bool = False
    safe_mode: bool = True


class CreateRunResponse(BaseModel):
    workspace_id: str
    run_id: str
    status: str


class RunStatusResponse(BaseModel):
    workspace_id: str
    run_id: str
    status: str
    detail: Optional[str] = None
    artifacts: Dict[str, Any] = {}
