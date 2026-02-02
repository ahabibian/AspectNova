def _parse_policy_decision(doc: Dict[str, Any]) -> DecisionSnapshot:
    schema_id = _get(doc, "schema_id", "")
    if schema_id != "policy-decision":
        raise ExecutorError(f"Unexpected policy schema_id: {schema_id!r} (expected 'policy-decision')")

    # Accept BOTH shapes:
    # A) nested: { "decision": { ... } }
    # B) flat/root: { "policy_id": ..., "priority": ..., ... }
    src = _get(doc, "decision", None)
    if isinstance(src, dict):
        d = src
    else:
        d = doc  # flat contract

    policy_id = str(_get(d, "policy_id", "")).strip()
    if not policy_id:
        raise ExecutorError("policy.decision.policy_id is required")

    policy_version = str(_get(d, "policy_version", DEFAULT_POLICY_VERSION)).strip() or DEFAULT_POLICY_VERSION

    priority = str(_get(d, "priority", "")).strip().lower()
    _req_in_set(priority, {"low", "medium", "high"}, "priority")

    risk_bucket = str(_get(d, "risk_bucket", "")).strip().upper()
    _req_in_set(risk_bucket, {"A", "B", "C"}, "risk_bucket")

    conf = _get(d, "confidence", 0.0)
    try:
        confidence = float(conf)
    except Exception:
        raise ExecutorError(f"policy.decision.confidence must be numeric, got: {conf!r}")
    if not (0.0 <= confidence <= 1.0):
        raise ExecutorError(f"policy.decision.confidence out of range [0..1]: {confidence}")

    return DecisionSnapshot(
        policy_id=policy_id,
        policy_version=policy_version,
        priority=priority,
        risk_bucket=risk_bucket,
        confidence=confidence,
    )
