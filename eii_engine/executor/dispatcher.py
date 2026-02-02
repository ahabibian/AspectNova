from __future__ import annotations

from typing import Any, Dict

from eii_engine.executor.actions.cleanup_candidates import run_cleanup_candidates


class UnsupportedActionError(Exception):
    pass


def execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action.get("type", "")
    if action_type == "cleanup.candidates.v1":
        return run_cleanup_candidates(action)

    raise UnsupportedActionError(f"Unsupported action.type: {action_type}")
