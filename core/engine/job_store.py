from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass(frozen=True)
class JobRef:
    root: Path
    workspace_id: str
    run_id: str

    @property
    def job_dir(self) -> Path:
        return self.root / ".aspectnova" / "jobs" / self.workspace_id / self.run_id

    @property
    def job_json(self) -> Path:
        return self.job_dir / "job.json"

    @property
    def logs_dir(self) -> Path:
        return self.job_dir / "logs"

    @property
    def stdout_log(self) -> Path:
        return self.logs_dir / "stdout.log"

    @property
    def stderr_log(self) -> Path:
        return self.logs_dir / "stderr.log"

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(p: Path, obj: Dict[str, Any]) -> None:
    ensure_dir(p.parent)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def init_job(root: Path, workspace_id: str, run_id: str, request: Dict[str, Any]) -> JobRef:
    ref = JobRef(root=root, workspace_id=workspace_id, run_id=run_id)
    ensure_dir(ref.logs_dir)

    job = {
        "workspace_id": workspace_id,
        "run_id": run_id,
        "status": "queued",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "request": request,
        "artifacts": {},
        "logs": {
            "stdout": str(ref.stdout_log),
            "stderr": str(ref.stderr_log),
        },
        "error": None,
    }
    write_json(ref.job_json, job)
    return ref

def update_job(ref: JobRef, **patch: Any) -> Dict[str, Any]:
    job = read_json(ref.job_json)
    job.update(patch)
    job["updated_at"] = utc_now_iso()
    write_json(ref.job_json, job)
    return job

def get_job(root: Path, workspace_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    ref = JobRef(root=root, workspace_id=workspace_id, run_id=run_id)
    if not ref.job_json.exists():
        return None
    return read_json(ref.job_json)
