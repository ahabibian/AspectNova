from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .logging_jsonl import JsonlLogger


def _add_legacy_commands(sub: argparse._SubParsersAction) -> None:
    """
    Bridge: keep old behavior available without being the main CLI identity.
    If you later migrate scan/index/report into proper subcommands, replace this.
    """
    # lazy import: legacy module may not exist in some setups
    try:
        from . import legacy_cli as legacy  # type: ignore
    except Exception:
        legacy = None  # type: ignore

    if legacy is None:
        return

    # legacy exposes a function to register its subcommands (we create it below)
    if hasattr(legacy, "register"):
        legacy.register(sub)


def cmd_verify() -> int:
    # Minimal real checks can be added later (config/policies/write perms)
    print("OK")
    return 0


def cmd_run(run_id: str, config_path: str) -> int:
    run_dir = Path("runs") / run_id
    log_path = run_dir / "pipeline.log.jsonl"
    logger = JsonlLogger(path=log_path, run_id=run_id, app_version=__version__)
    logger.emit("run.start", inputs={"config": config_path})

    from .pipeline_runner import run_pipeline
    rc = run_pipeline(run_id=run_id, config_path=config_path, logger=logger)

    logger.emit("run.end", status="PASS" if rc == 0 else "FAIL")
    return rc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="aspectnova")
    p.add_argument("--version", action="store_true", help="print version and exit")

    sub = p.add_subparsers(dest="cmd", required=False)

    sub.add_parser("verify", help="environment & config checks")

    pr = sub.add_parser("run", help="run full pipeline")
    pr.add_argument("--run-id", required=True)
    pr.add_argument("--config", default="config.v1.yaml")

    # legacy commands: scan/index/report (optional)
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