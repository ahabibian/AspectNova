from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from pathlib import Path

def job_dir(root: Path, workspace_id: str) -> Path:
    return Path(root) / ".aspectnova" / "contracts" / workspace_id


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(p: Path) -> Dict[str, Any]:
    """
    Robust JSON reader:
    - tolerates UTF-8 BOM (utf-8-sig)
    """
    txt = p.read_text(encoding="utf-8-sig")
    return json.loads(txt)


def write_json(p: Path, data: Dict[str, Any]) -> None:
    """
    Writes JSON without BOM, stable formatting.
    """
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class JobRef:
    root: Path
    workspace_id: str
    run_id: str

    @property
    def jobs_root(self) -> Path:
        return self.root / ".aspectnova" / "jobs"

    @property
    def job_dir(self) -> Path:
        return self.jobs_root / self.workspace_id / self.run_id

    @property
    def logs_dir(self) -> Path:
        return self.job_dir / "logs"

    @property
    def job_json(self) -> Path:
        return self.job_dir / "job.json"

    @property
    def stdout_log(self) -> Path:
        return self.logs_dir / "stdout.log"

    @property
    def stderr_log(self) -> Path:
        return self.logs_dir / "stderr.log"


def ref(root: Path, workspace_id: str, run_id: str) -> JobRef:
    return JobRef(root=Path(root).resolve(), workspace_id=workspace_id, run_id=run_id)


def init_job(*, root: Path, workspace_id: str, run_id: str, request: Dict[str, Any]) -> JobRef:
    """
    Creates the job directory + initial job.json and empty logs.
    IMPORTANT: keyword-only args to match runs.py calls.
    """
    r = ref(root, workspace_id, run_id)

    ensure_dir(r.logs_dir)

    # create empty logs if not exist
    if not r.stdout_log.exists():
        r.stdout_log.write_text("", encoding="utf-8")
    if not r.stderr_log.exists():
        r.stderr_log.write_text("", encoding="utf-8")

    job = {
        "workspace_id": workspace_id,
        "run_id": run_id,
        "status": "queued",  # API may set "created" afterwards
        "created_at": utc_now_z(),
        "updated_at": utc_now_z(),
        "request": request or {},
        "artifacts": {},
        "logs": {
            "stdout": str(r.stdout_log),
            "stderr": str(r.stderr_log),
        },
        "error": None,
    }
    write_json(r.job_json, job)
    return r


def get_job(*, root: Path, workspace_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    r = ref(root, workspace_id, run_id)
    if not r.job_json.exists():
        return None
    return read_json(r.job_json)


def update_job(
    r: JobRef,
    *,
    status: Optional[str] = None,
    error: Optional[str] = None,
    artifacts: Optional[Dict[str, Any]] = None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    job = read_json(r.job_json)

    if status is not None:
        job["status"] = status
    # error can be explicitly set to None
    job["error"] = error

    if artifacts is not None:
        job["artifacts"] = artifacts

    if request is not None:
        job["request"] = request

    job["updated_at"] = utc_now_z()
    write_json(r.job_json, job)
    return job


def append_log(r: JobRef, stream: str, line: str) -> None:
    """
    stream: "stdout" | "stderr"
    """
    ensure_dir(r.logs_dir)
    p = r.stdout_log if stream == "stdout" else r.stderr_log
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line.rstrip("\n") + "\n")
