# ADR-003: Cleanup Engine is Simulation-Only (aspectnova.cleanup_proposal.v1)
Date: 2026-01-07
Status: Accepted
Owners: AspectNova Core Team

## Context
We need a reliable engine that produces actionable recommendations without executing changes on user devices by default. Enterprise customers require:
- Review/approval workflows
- Clear audit trails and reversible actions
- Separation between "proposal" and "execution"

## Decision
The Cleanup Engine produces **simulation output only**:
- Output schema: `schema_version = "aspectnova.cleanup_proposal.v1"`
- The engine generates a list of recommended actions:
  - `SUGGEST_DELETE`, `SUGGEST_ARCHIVE`, `SUGGEST_MOVE`, `SUGGEST_DEDUP`, `SUGGEST_REVIEW`
- Each action includes:
  - targets (file_ids / duplicate_cluster_id)
  - confidence (0..1)
  - risk (level + reversible flag)
  - rationale (rule_ids + signals_used + explanation)

Execution is a separate phase (future ADR):
- A proposal can be converted into a signed command set only after approval and authorization.

## Consequences
- UI can safely display recommendations and approvals without having device write permissions.
- Agents can remain read-only until command flow is explicitly enabled.
- Auditability improves: every recommendation is explainable and traceable to rules.

## Non-Goals
- Automatic deletion/move on devices in the default system.
- Embedding raw paths/names in proposals.

## Security / Audit Notes
- Proposals must reference only canonical identifiers (file_id, duplicate_cluster_id).
- Proposal generation logs must record engine/ruleset version for reproducibility.
