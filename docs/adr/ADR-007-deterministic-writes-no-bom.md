# ADR-007 — Deterministic Writes & No-BOM Policy

Status: Accepted  
Date: 2026-02-27  

---

## Context

Previous regressions occurred due to:
- UTF-8 BOM insertion
- PowerShell default encoding
- Non-deterministic ordering
- Implicit filesystem writes

This caused:
- Hash drift
- Pipeline instability
- Reproducibility failures

---

## Decision

All writes must:

1. Use UTF-8 without BOM
2. Be deterministic
3. Avoid implicit encoding
4. Use approved write helpers only

DEVGUARD enforces:
- No Set-Content
- No Out-File
- No >> redirection

---

## Consequences

Pros:
- Stable pipeline output
- Reproducible hashes
- CI-safe

Cons:
- Slightly more verbose write logic
- Strict discipline required

---

## Enforcement

- Gate execution
- DEVGUARD
- Code review

No exceptions.