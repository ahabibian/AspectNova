from __future__ import annotations

from typing import Any, Dict, List

from eii_engine.contracts_loader import load_capability, load_schema
from eii_engine.validation import validate_json, ValidationError
from eii_engine.runner.guardrails import decide_action_execution
from eii_engine.executor.dispatcher import execute_action, UnsupportedActionError


def run_steps(
    *,
    execution_plan: Dict[str, Any],
    contracts_root: str,
    runner_state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns a step_results bundle you can embed into your existing execution_report v0.
    """

    action_contract_schema = load_schema(contracts_root, "schemas/action_contract.v1.json")

    step_results: List[Dict[str, Any]] = []

    def record_step(step_id: str, *, status: str, reasons=None, output=None, capability=None):
        step_results.append({
            "step_id": step_id,
            "status": status,
            "reasons": reasons or [],
            "capability_snapshot": capability or None,
            "output": output or None
        })

    steps = execution_plan.get("steps", [])
    for step in steps:
        step_id = step.get("step_id", "unknown_step")
        action = step.get("action")

        if not isinstance(action, dict):
            record_step(step_id, status="FAILED_VALIDATION", reasons=["step.action missing or not an object"])
            continue

        # 1) Validate action contract
        try:
            validate_json(action, action_contract_schema, label="action_contract")
        except ValidationError as e:
            record_step(step_id, status="FAILED_VALIDATION", reasons=[str(e)])
            continue

        # 2) Load capability
        try:
            cap = load_capability(contracts_root, action["type"])
            # Sanity: ensure cap matches action
            if cap.get("action_type") != action["type"]:
                record_step(step_id, status="FAILED_VALIDATION",
                            reasons=[f"capability.action_type mismatch: {cap.get('action_type')} != {action['type']}"])
                continue
        except Exception as e:
            record_step(step_id, status="SKIPPED_UNSUPPORTED_ACTION", reasons=[str(e)])
            continue

        # 3) Validate inputs with capability schema
        try:
            inputs_schema_rel = cap["io"]["inputs_schema"]
            inputs_schema = load_schema(contracts_root, inputs_schema_rel)
            validate_json(action.get("inputs", {}), inputs_schema, label=f"{action['type']}.inputs")
        except Exception as e:
            record_step(step_id, status="FAILED_VALIDATION", reasons=[str(e)], capability=cap)
            continue

        # 4) Guardrails decision
        decision = decide_action_execution(
            action=action,
            runner_state=runner_state,
            capability=cap
        )

        if not decision.should_execute:
            record_step(step_id, status=decision.status, reasons=decision.reasons, capability=cap)
            continue

        # 5) Execute action
        try:
            output = execute_action(action)
        except UnsupportedActionError as e:
            record_step(step_id, status="SKIPPED_UNSUPPORTED_ACTION", reasons=[str(e)], capability=cap)
            continue
        except Exception as e:
            record_step(step_id, status="FAILED_RUNTIME", reasons=[str(e)], capability=cap)
            continue

        # 6) Validate outputs with capability schema
        try:
            outputs_schema_rel = cap["io"]["outputs_schema"]
            outputs_schema = load_schema(contracts_root, outputs_schema_rel)
            validate_json(output, outputs_schema, label=f"{action['type']}.outputs")
        except Exception as e:
            record_step(step_id, status="FAILED_VALIDATION", reasons=[str(e)], capability=cap)
            continue

        record_step(step_id, status="EXECUTED_OK", output=output, capability=cap)

    return {
        "runner_state": runner_state,
        "step_results": step_results
    }
