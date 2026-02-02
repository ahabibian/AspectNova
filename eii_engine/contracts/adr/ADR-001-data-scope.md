# ADR-001: Data Scope & Privacy Posture (Default L0/L1, Optional L2)
Date: 2026-01-07
Status: Accepted
Owners: AspectNova Core Team

## Context
AspectNova processes device/file scan outputs for digital cleanup insights. The product is positioned as an enterprise-grade SaaS, where procurement/legal/security requirements frequently block content ingestion and raw path storage.

The system already supports stable import pipeline, KPI v2, device ownership, idempotency, and UI formatting. Next steps require a formal data scope decision to anchor schema, engine design, and auditability.

## Decision
1) Default operating mode is **Privacy-first**:
   - Allowed data levels: **L0 + L1**
   - The platform **does not store file contents**, extracted text, embeddings, thumbnails, or full raw paths by default.

2) **Actionable / content-derived processing** is an explicit **org policy opt-in (L2)**:
   - Requires a separate, explicit organization-level policy and contractual allowance.
   - When disabled, payloads containing content-derived fields MUST be rejected or stripped at ingestion.

3) Raw file paths and raw file names are not stored:
   - Only tokenized/classified location indicators are allowed (e.g., location_class, path_token).
   - File identifiers are stable, agent-generated references (e.g., HMAC-based), not raw paths.

## Consequences
- The canonical agent payload schema must encode:
  - `policy.data_level`, `policy.content_allowed`, and path-handling constraints.
- Ingestion must enforce scope:
  - schema validation + server-side policy enforcement (never UI-only).
- Cleanup Engine must be capable of providing useful recommendations using only metadata and derived signals.
- L2 features may be added later without breaking the system by using explicit policy gates and versioned schemas.

## Non-Goals
- Building content classification, PII detection, or semantic understanding in the default mode.
- Relying on UI for privacy guarantees.

## Compliance / Audit Notes
- Data retention: scan raw events limited; aggregated KPIs retained longer (configurable per org).
- Policy decisions are auditable via ADRs + schema versions + enforcement logs.
