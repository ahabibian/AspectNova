# ADR-004: Execution gate min_actions is conditional on command_plan.actions

## Context
Execution stage may legitimately perform zero actions when upstream command_plan has zero actions (e.g., findings == 0).
Previous policy enforcement required min_actions >= 1 unconditionally, causing false FAIL.

## Decision
gate_execution reads runs/<run_id>/output/evidence/command_plan.json when available.
If command_plan.actions == 0 => effective min_actions = 0.
Otherwise enforce policy.requirements.min_actions as-is.

## Consequences
- Prevents false negatives for no-finding runs.
- Still enforces min_actions when work is expected.
- Introduces a clear cross-stage contract: execution expectations derive from command_plan.

## Status
Accepted
