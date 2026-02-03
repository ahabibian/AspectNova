from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from core.engine.job_store import JobRef, update_job
from core.storage.paths import WorkspacePaths

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"

def _run_cmd(ref: JobRef, args: list[str]) -> None:
    """
    Runs a command, appends stdout/stderr to job logs.
    Raises RuntimeError on non-zero exit.
    """
    # NOTE: We append logs to keep a single log per run.
    with ref.stdout_log.open("a", encoding="utf-8") as out, ref.stderr_log.open("a", encoding="utf-8") as err:
        out.write("\n\n=== CMD: " + " ".join(args) + "\n")
        out.flush()
        p = subprocess.run(args, stdout=out, stderr=err, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"command failed exit={p.returncode}: {' '.join(args)}")

def run_archive_job(
    ref: JobRef,
    *,
    mode: str,
    root: Path,
    workspace_id: str,
    run_id: str,
    rules_path: Path,
    scan_path: Optional[Path],
    targets_path: Optional[Path],
    execute: bool,
    safe_mode: bool,
    archive_base: Optional[Path],
) -> Dict[str, Any]:
    """
    Behavior preserved:
    - full: extractor -> targets.json -> executor -> payload.zip + trace_contract + execution_report
    - safe: executor only (requires targets_path)
    """
    update_job(ref, status="running")

    paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)

    # Standard artifact locations (API can return these)
    out_dir = ref.job_dir / "out"
    out_targets = out_dir / "cleanup_targets.json"
    out_report = out_dir / "execution_report.json"

    try:
        # 1) Extract (full mode)
        if mode == "full":
            if not scan_path:
                raise RuntimeError("full mode requires scan_path")
            cmd = [
                sys.executable,
                str(TOOLS_DIR / "extract_cleanup_targets_v1_1.py"),
                "--scan", str(scan_path),
                "--rules", str(rules_path),
                "--out", str(out_targets),
                "--root", str(root),
            ]
            _run_cmd(ref, cmd)
            if not out_targets.exists():
                raise RuntimeError("extractor did not produce cleanup_targets.json")
            targets_for_exec = out_targets

        elif mode == "safe":
            if not targets_path:
                raise RuntimeError("safe mode requires targets_path")
            targets_for_exec = targets_path

        else:
            raise RuntimeError(f"invalid mode: {mode}")

        # 2) Execute (archive)
        exec_cmd = [
            sys.executable,
            str(TOOLS_DIR / "execute_cleanup_plan_v1_1.py"),
            "--targets", str(targets_for_exec),
            "--rules", str(rules_path),
            "--root", str(root),
            "--workspace-id", workspace_id,
            "--run-id", run_id,
            "--out-report", str(out_report),
        ]

        if archive_base:
            exec_cmd += ["--archive-base", str(archive_base)]
        if execute:
            exec_cmd += ["--execute"]
        if safe_mode:
            exec_cmd += ["--safe-mode"]

        _run_cmd(ref, exec_cmd)

        # 3) Artifacts map (what API returns)
        artifacts = {
            "job_out_dir": str(out_dir),
            "targets_path": str(out_targets) if out_targets.exists() else (str(targets_path) if targets_path else None),
            "execution_report": str(out_report) if out_report.exists() else None,
            "archive_dir": str(paths.archive_dir),
            "payload_zip": str(paths.payload_zip_path),
            "manifest": str(paths.manifest_path),
            "contracts_dir": str(paths.contracts_dir),
            "trace_contract": str(paths.trace_contract_path),
        }

        update_job(ref, status="succeeded", artifacts=artifacts, error=None)
        return {"ok": True, "artifacts": artifacts}

    except Exception as e:
        update_job(ref, status="failed", error=str(e))
        raise
