from __future__ import annotations
import argparse

def register(sub: argparse._SubParsersAction) -> None:
    """
    Provide backward-compatible commands: scan/index/report.
    This expects your existing logic is importable from existing modules.
    If not available, remove this file later.
    """
    # NOTE: adjust these imports to your actual old functions if needed.
    # For now we create placeholders that clearly fail with guidance.

    def _missing(name: str):
        def _run(_args):
            raise SystemExit(f"Legacy command '{name}' not wired yet. Use: aspectnova run ...")
        return _run

    for name in ("scan", "index", "report"):
        sp = sub.add_parser(name, help=f"legacy {name} (temporary)")
        sp.set_defaults(_fn=_missing(name))
