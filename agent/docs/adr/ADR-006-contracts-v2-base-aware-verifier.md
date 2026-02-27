# ADR-006: Stage contracts v2 + base-aware verification

## Context
Stage outputs are not uniformly located. Most artifacts are under runs/<run_id>/output/evidence, while scan_normalizer writes canonical scan_result artifacts under runs/<run_id>/output.
A single contracts file must describe reality without hacks or manual overrides.

## Decision
- Introduce contracts/stage_contracts.v2.yml as the canonical contracts registry.
- Add per-stage ase to allow output vs evidence roots.
- Update tools/verify_contracts.py to default to v2 and verify artifacts using each stage base.

## Consequences
- Contracts become stable and versioned.
- Verification matches the real pipeline.
- Enables future migration to a single base (all-evidence) without breaking verification (just update v2).
## Status
Accepted
