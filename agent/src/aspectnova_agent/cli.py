from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .logging_jsonl import JsonlLogger


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_run_meta(meta_path: Path) -> dict:
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def save_run_meta(meta_path: Path, payload: dict) -> None:
    meta_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_run_meta(meta_path: Path, **fields) -> dict:
    meta = load_run_meta(meta_path)
    meta.update(fields)
    meta["updated_at_utc"] = utc_now_iso()
    save_run_meta(meta_path, meta)
    return meta


def _add_legacy_commands(sub: argparse._SubParsersAction) -> None:
    """
    Bridge: keep old behavior available without being the main CLI identity.
    If you later migrate scan/index/report into proper subcommands, replace this.
    """
    try:
        from . import legacy_cli as legacy  # type: ignore
    except Exception:
        legacy = None  # type: ignore

    if legacy is None:
        return

    if hasattr(legacy, "register"):
        legacy.register(sub)


def cmd_verify() -> int:
    print("OK")
    return 0


def cmd_run(run_id: str, config_path: str) -> int:
    run_dir = Path("runs") / run_id
    meta_path = run_dir / "run.meta.json"
    evidence_dir = run_dir / "output" / "evidence"
    log_path = run_dir / "pipeline.log.jsonl"

    if not run_dir.exists():
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "where": "run_precheck",
                    "reason": "run_dir_missing",
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    logger = JsonlLogger(path=log_path, run_id=run_id, app_version=__version__)
    logger.emit("run.start", inputs={"config": config_path})

    update_run_meta(
        meta_path,
        run_id=run_id,
        state="running",
        last_status="RUNNING",
        last_reason=None,
        config_path=config_path,
        engine="aspectnova_agent.cli",
        version="dv-run-meta.v1",
    )

    try:
        from .pipeline_runner import run_pipeline
        rc = run_pipeline(run_id=run_id, config_path=config_path, logger=logger)

        if rc == 0:
            update_run_meta(
                meta_path,
                state="finalized",
                last_status="PASS",
                last_reason=None,
                evidence_dir=str(evidence_dir),
            )
        else:
            update_run_meta(
                meta_path,
                state="blocked",
                last_status="FAIL",
                last_reason=f"pipeline_returncode_{rc}",
                evidence_dir=str(evidence_dir),
            )

        logger.emit("run.end", status="PASS" if rc == 0 else "FAIL", returncode=rc)
        return rc

    except Exception as e:
        update_run_meta(
            meta_path,
            state="failed",
            last_status="ERROR",
            last_reason=str(e),
            evidence_dir=str(evidence_dir),
        )
        logger.emit("run.end", status="ERROR", reason=str(e))
        raise


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="aspectnova")
    p.add_argument("--version", action="store_true", help="print version and exit")

    sub = p.add_subparsers(dest="cmd", required=False)

    sub.add_parser("verify", help="environment & config checks")

    pr = sub.add_parser("run", help="run full pipeline")
    pr.add_argument("--run-id", required=True)
    pr.add_argument("--config", default="config.v1.yaml")

    _add_legacy_commands(sub)

    args = p.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.cmd == "verify":
        return cmd_verify()

    if args.cmd == "run":
        return cmd_run(run_id=args.run_id, config_path=args.config)

    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())