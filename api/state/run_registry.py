# api/state/run_registry.py
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class RunRecord:
    workspace_id: str
    run_id: str
    status: str
    created_at: float
    updated_at: float
    request: Dict[str, Any]
    detail: Optional[str] = None
    artifacts: Dict[str, Any] = None

class RunRegistry:
    """
    Filesystem registry:
      .aspectnova/api_state/workspaces/{ws}/runs/{run_id}.json
    """
    def __init__(self, root: Path):
        self.root = root
        self.base = root / ".aspectnova" / "api_state" / "workspaces"
        self.base.mkdir(parents=True, exist_ok=True)

    def _run_path(self, workspace_id: str, run_id: str) -> Path:
        p = self.base / workspace_id / "runs"
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{run_id}.json"

    def create(self, workspace_id: str, request: Dict[str, Any]) -> RunRecord:
        run_id = time.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:10]
        now = time.time()
        rec = RunRecord(
            workspace_id=workspace_id,
            run_id=run_id,
            status="created",
            created_at=now,
            updated_at=now,
            request=request,
            detail=None,
            artifacts={},
        )
        self.save(rec)
        return rec

    def load(self, workspace_id: str, run_id: str) -> RunRecord:
        p = self._run_path(workspace_id, run_id)
        if not p.exists():
            raise FileNotFoundError(str(p))
        data = json.loads(p.read_text(encoding="utf-8"))
        return RunRecord(**data)

    def save(self, rec: RunRecord) -> None:
        p = self._run_path(rec.workspace_id, rec.run_id)
        data = {
            "workspace_id": rec.workspace_id,
            "run_id": rec.run_id,
            "status": rec.status,
            "created_at": rec.created_at,
            "updated_at": rec.updated_at,
            "request": rec.request,
            "detail": rec.detail,
            "artifacts": rec.artifacts or {},
        }
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_status(self, workspace_id: str, run_id: str, status: str, detail: Optional[str] = None, artifacts: Optional[Dict[str, Any]] = None) -> RunRecord:
        rec = self.load(workspace_id, run_id)
        now = time.time()
        new = RunRecord(
            workspace_id=rec.workspace_id,
            run_id=rec.run_id,
            status=status,
            created_at=rec.created_at,
            updated_at=now,
            request=rec.request,
            detail=detail if detail is not None else rec.detail,
            artifacts=artifacts if artifacts is not None else (rec.artifacts or {}),
        )
        self.save(new)
        return new
