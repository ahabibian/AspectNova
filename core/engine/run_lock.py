from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_dir(root: Path, workspace_id: str, run_id: str) -> Path:
    return root / ".aspectnova" / "contracts" / workspace_id / run_id


def lock_path(root: Path, workspace_id: str, run_id: str) -> Path:
    return run_dir(root, workspace_id, run_id) / "run.lock.json"


def approval_path(root: Path, workspace_id: str, run_id: str) -> Path:
    return run_dir(root, workspace_id, run_id) / "approval.json"


def ensure_locked(root: Path, workspace_id: str, run_id: str) -> Dict[str, Any]:
    d = run_dir(root, workspace_id, run_id)
    d.mkdir(parents=True, exist_ok=True)
    p = lock_path(root, workspace_id, run_id)

    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))

    data = {
        "schema_version": "v1",
        "workspace_id": workspace_id,
        "run_id": run_id,
        "state": "locked",
        "locked_at": utc_now_iso(),
    }
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def set_lock_state(root: Path, workspace_id: str, run_id: str, state: str) -> Dict[str, Any]:
    d = run_dir(root, workspace_id, run_id)
    d.mkdir(parents=True, exist_ok=True)
    p = lock_path(root, workspace_id, run_id)

    data = {
        "schema_version": "v1",
        "workspace_id": workspace_id,
        "run_id": run_id,
        "state": state,
        "updated_at": utc_now_iso(),
    }
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def is_approved(root: Path, workspace_id: str, run_id: str) -> bool:
    p = approval_path(root, workspace_id, run_id)
    if not p.exists():
        return False

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("approved") is True
    except Exception:
        return False


def approve(root: Path, workspace_id: str, run_id: str, confirm_secret: str) -> Dict[str, Any]:
    env = (os.environ.get("ASPECTNOVA_ENV") or "dev").strip().lower()
    expected = os.environ.get("ASPECTNOVA_APPROVAL_SECRET", "")

    if env != "prod":
        ok = True
    else:
        ok = bool(expected) and (confirm_secret == expected)

    if not ok:
        raise ValueError("Invalid approval secret")

    d = run_dir(root, workspace_id, run_id)
    d.mkdir(parents=True, exist_ok=True)

    data = {
        "schema_version": "v1",
        "workspace_id": workspace_id,
        "run_id": run_id,
        "approved": True,
        "approved_at": utc_now_iso(),
        "mode": env,
    }

    approval_path(root, workspace_id, run_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    set_lock_state(root, workspace_id, run_id, "approved")
    return data
