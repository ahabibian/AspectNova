from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .logging_jsonl import JsonlLogger


def run_pipeline(run_id: str, config_path: str, logger: JsonlLogger) -> int:
    """
    Bridge to the repo root runner.
    NOTE: root run_pipeline.py currently does NOT accept --config, so config_path is logged only.
    """
    repo_root = Path(__file__).resolve().parents[2]  # .../agent
    runner = repo_root / "run_pipeline.py"

    if not runner.exists():
        logger.emit("run.fail", reason="runner_missing", runner=str(runner))
        raise FileNotFoundError(f"Missing root runner: {runner}")

    # Keep config in log (for traceability) even if runner doesn't accept it yet.
    cmd = [sys.executable, str(runner), "--run-id", run_id]
    logger.emit("subprocess.start", cmd=cmd, cwd=str(repo_root), config=config_path)

    p = subprocess.run(cmd, cwd=str(repo_root))
    logger.emit("subprocess.end", returncode=p.returncode)
    return int(p.returncode)
