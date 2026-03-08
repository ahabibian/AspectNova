from __future__ import annotations

import sys
from pathlib import Path

from dv.scanner.scanner import WorkspaceScanner, build_run_output_dir
from dv.evidence.manifest_builder import ManifestBuilder
from dv.scoring.scoring_engine import ScoringEngine
from dv.policy.policy_engine import PolicyEngine
from dv.verdict.verdict_engine import VerdictEngine
from dv.report.report_engine import ReportEngine
from dv.planner.cleanup_planner import CleanupPlanner
from dv.packager.packager import DVPackager


def run_pipeline(
    workspace: Path,
    runs_dir: Path,
    hash_small_files: bool = True,
    hash_max_mb: int = 10,
) -> int:
    if not workspace.exists():
        print(f"ERROR: workspace does not exist: {workspace}", file=sys.stderr)
        return 2

    if not workspace.is_dir():
        print(f"ERROR: workspace is not a directory: {workspace}", file=sys.stderr)
        return 2

    output_dir = build_run_output_dir(runs_dir)

    print("== DV RUN: SCAN ==")
    scanner = WorkspaceScanner(
        workspace=workspace,
        output_dir=output_dir,
        hash_small_files=hash_small_files,
        hash_max_size_bytes=hash_max_mb * 1024 * 1024,
    )
    run_meta = scanner.write_outputs()

    print("== DV RUN: MANIFEST ==")
    ManifestBuilder(output_dir=output_dir).build()

    print("== DV RUN: SCORING ==")
    ScoringEngine(output_dir=output_dir).build()

    print("== DV RUN: POLICY ==")
    PolicyEngine(output_dir=output_dir).build()

    print("== DV RUN: VERDICT ==")
    VerdictEngine(output_dir=output_dir).build()

    print("== DV RUN: REPORT ==")
    ReportEngine(output_dir=output_dir).build()

    print("== DV RUN: CLEANUP PLAN ==")
    CleanupPlanner(output_dir=output_dir).build()

    print("== DV RUN: PACKAGE ==")
    artifact_path, _ = DVPackager(run_output=output_dir).package()

    print("")
    print("DV RUN COMPLETE")
    print(f"Run ID: {run_meta.run_id}")
    print(f"Workspace: {run_meta.workspace_root}")
    print(f"Output dir: {output_dir}")
    print(f"Artifact: {artifact_path}")

    return 0
