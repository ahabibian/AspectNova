# core/engine/runner.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from core.engine.job_store import JobRef, update_job, ensure_dir
from core.storage.paths import WorkspacePaths


def _run_cmd(cmd: list[str], stdout_path: Path, stderr_path: Path) -> int:
    ensure_dir(stdout_path.parent)
    ensure_dir(stderr_path.parent)

    with stdout_path.open("a", encoding="utf-8") as out, stderr_path.open("a", encoding="utf-8") as err:
        p = subprocess.Popen(cmd, stdout=out, stderr=err)
        p.wait()
        return p.returncode


def execute_job(ref: JobRef, request: Dict[str, Any]) -> None:
    root = Path(request["root"]).resolve()
    scan_path = Path(request["scan_path"]).resolve()
    rules_path = Path(request["rules_path"]).resolve()

    workspace_id = ref.workspace_id
    run_id = ref.run_id

    paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)

    update_job(ref, status="running", error=None)

    out_targets = paths.contracts_dir / "cleanup_targets.json"
    extract_cmd = [
        sys.executable,
        "tools/extract_cleanup_targets_v1_1.py",
        "--scan", str(scan_path),
        "--rules", str(rules_path),
        "--out", str(out_targets),
        "--root", str(root),
    ]

    code = _run_cmd(extract_cmd, ref.stdout_log, ref.stderr_log)
    if code != 0:
        update_job(ref, status="failed", error="extract step failed")
        return

    if not out_targets.exists():
        update_job(ref, status="failed", error="extractor did not produce cleanup_targets.json")
        return

    out_report = paths.contracts_dir / "execution_report.json"

    exec_cmd = [
        sys.executable,
        "tools/execute_cleanup_plan_v1_1.py",
        "--targets", str(out_targets),
        "--rules", str(rules_path),
        "--root", str(root),
        "--workspace-id", workspace_id,
        "--run-id", run_id,
        "--out-report", str(out_report),
    ]

    if bool(request.get("safe_mode", True)):
        exec_cmd.append("--safe-mode")

    if bool(request.get("remove_original", False)):
        exec_cmd.append("--remove-original")

    if bool(request.get("execute", False)):
        exec_cmd.append("--execute")

        confirm_secret = request.get("confirm_secret")
        if confirm_secret is None:
            confirm_secret = ""
        exec_cmd.extend(["--confirm-secret", str(confirm_secret)])

    code = _run_cmd(exec_cmd, ref.stdout_log, ref.stderr_log)
    if code != 0:
        update_job(ref, status="failed", error="execution step failed")
        return

    update_job(
        ref,
        status="completed",
        artifacts={
            "contracts_dir": str(paths.contracts_dir),
            "archive_dir": str(paths.archive_dir),
            "targets_json": str(out_targets),
            "execution_report": str(out_report),
        },
        error=None,
    )
