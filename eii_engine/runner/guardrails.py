from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class GuardrailDecision:
    should_execute: bool
    status: str
    reasons: List[str]
    capability: Optional[Dict[str, Any]] = None


def decide_action_execution(
    *,
    action: Dict[str, Any],
    runner_state: Dict[str, Any],
    capability: Dict[str, Any],
) -> GuardrailDecision:
    reasons: List[str] = []

    safe_mode = bool(runner_state.get("safe_mode", True))
    execute_requested = bool(runner_state.get("execute_requested", False))
    confirm_received = bool(runner_state.get("confirm_received", False))

    if not execute_requested:
        return GuardrailDecision(
            should_execute=False,
            status="SKIPPED_EXECUTE_NOT_REQUESTED",
            reasons=["execute_requested=false"],
            capability=capability,
        )

    action_guards = action.get("guards", {}) or {}
    cap_guards = capability.get("guards", {}) or {}

    # strictest wins
    requires_confirm = bool(action_guards.get("requires_confirm", False)) or bool(
        cap_guards.get("requires_confirm", False)
    )
    requires_safe_mode = bool(action_guards.get("requires_safe_mode", False)) or bool(
        cap_guards.get("requires_safe_mode", False)
    )

    action_allowed_modes = set(action_guards.get("allowed_modes", []) or [])
    cap_allowed_modes = set(cap_guards.get("allowed_modes", []) or [])
    if not action_allowed_modes or not cap_allowed_modes:
        return GuardrailDecision(
            should_execute=False,
            status="FAILED_VALIDATION",
            reasons=["allowed_modes missing in action or capability"],
            capability=capability,
        )

    allowed_modes = action_allowed_modes.intersection(cap_allowed_modes)
    mode = action.get("mode", "")

    if mode not in allowed_modes:
        return GuardrailDecision(
            should_execute=False,
            status="SKIPPED_GUARDRAIL_VIOLATION",
            reasons=[f"mode_not_allowed: {mode} not in {sorted(allowed_modes)}"],
            capability=capability,
        )

    if requires_safe_mode and not safe_mode:
        return GuardrailDecision(
            should_execute=False,
            status="SKIPPED_GUARDRAIL_VIOLATION",
            reasons=["requires_safe_mode=true but runner safe_mode=false"],
            capability=capability,
        )

    if requires_confirm and not confirm_received:
        return GuardrailDecision(
            should_execute=False,
            status="SKIPPED_CONFIRM_REQUIRED",
            reasons=["requires_confirm=true but confirm_received=false"],
            capability=capability,
        )

    # milestone safety belt: we still block any capability that declares write/delete
    eff_fs = ((capability.get("effects") or {}).get("filesystem") or {})
    if bool(eff_fs.get("write", False)) or bool(eff_fs.get("delete", False)):
        return GuardrailDecision(
            should_execute=False,
            status="SKIPPED_GUARDRAIL_VIOLATION",
            reasons=["milestone_block: write/delete effects not allowed yet"],
            capability=capability,
        )

    return GuardrailDecision(
        should_execute=True,
        status="EXECUTE_ALLOWED",
        reasons=["guardrails_ok"],
        capability=capability,
    )
