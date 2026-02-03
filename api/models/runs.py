from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any

RunMode = Literal["safe", "full"]

class RunCreateRequest(BaseModel):
    root: str = Field(..., description="Filesystem root where .aspectnova lives / or target root")
    mode: RunMode = Field(..., description="safe=execute only, full=extract+execute")
    # full mode inputs:
    scan_path: Optional[str] = Field(None, description="Path to scan_result.json (or scan payload) for extractor")
    # both modes:
    rules_path: str = Field(..., description="Path to policy YAML used by executor/extractor")
    # safe mode input:
    targets_path: Optional[str] = Field(None, description="Path to cleanup_targets.json for safe mode")
    # execution behavior:
    execute: bool = Field(False, description="If true, performs actions; otherwise dry-run/safe")
    safe_mode: bool = Field(True, description="Passed to executor to enforce safety semantics")
    archive_base: Optional[str] = Field(None, description="Optional override for archive base dir")

    # run identity:
    run_id: Optional[str] = Field(None, description="If provided, use this run_id; else auto-generated")

class RunCreateResponse(BaseModel):
    workspace_id: str
    run_id: str
    status: str

class RunStatusResponse(BaseModel):
    workspace_id: str
    run_id: str
    status: str
    created_at: str
    updated_at: str
    request: Dict[str, Any]
    artifacts: Dict[str, Any]
    logs: Dict[str, Any]
    error: Optional[str] = None
