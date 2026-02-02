# ADR-002: Versioned Agent Payload Contract (aspectnova.scan_payload.v1)
Date: 2026-01-07
Status: Accepted
Owners: AspectNova Core Team

## Context
We need a stable, versioned contract between Agents and the Core ingestion system. The contract must support:
- Enterprise procurement constraints (privacy-first default)
- Idempotent ingestion
- Chunked delivery for large scans
- Forward-compatible evolution without breaking old agents
- Separation of concerns: payload validation belongs to Core, not UI

## Decision
Adopt a canonical, versioned JSON schema:
- `schema_version = "aspectnova.scan_payload.v1"`
- Envelope sections:
  - `meta` (producer identity, timestamps, trace)
  - `context` (org/workspace/device identifiers)
  - `policy` (data scope declaration; enforced by server)
  - `idempotency` (dedupe window & key)
  - `scan` (scan identifiers, summary, KPI block, chunk, optional items list)
  - `extensions` (forward-compatible map)

Privacy constraints:
- No raw full paths or raw file names stored in the canonical model.
- Content-derived fields appear only under `content` and are allowed only if `policy.content_allowed=true`.

## Consequences
- The ingestion pipeline MUST:
  1) Validate payload against JSON schema.
  2) Enforce org policy (server-side), overriding payload claims if needed.
  3) Normalize into internal canonical storage model.
- Agents implement payload creation according to the schema; unknown future fields go into `extensions`.
- KPI v2 is carried as a flexible object in v1 and can be separately versioned/referenced later.

## Non-Goals
- Encoding every KPI v2 field in this schema now (kept evolvable).
- Tying payload schema to UI formatting decisions.

## Operational Notes
- `idempotency.key` is required and must be stable for retries.
- `scan.chunk` enables multi-part uploads and reliable reassembly.
