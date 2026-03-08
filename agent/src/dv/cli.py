from __future__ import annotations

import argparse
from pathlib import Path

from dv.runner import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dv",
        description="Data Verdict CLI",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run full DV pipeline")
    run_parser.add_argument(
        "--workspace",
        required=True,
        help="Path to workspace root",
    )
    run_parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Base runs directory (default: runs)",
    )
    run_parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Disable sha256 hashing for small files",
    )
    run_parser.add_argument(
        "--hash-max-mb",
        type=int,
        default=10,
        help="Hash only files up to this size in MB (default: 10)",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        return run_pipeline(
            workspace=Path(args.workspace),
            runs_dir=Path(args.runs_dir),
            hash_small_files=not args.no_hash,
            hash_max_mb=args.hash_max_mb,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
