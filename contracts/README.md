# AspectNova Contracts Root

This directory is the canonical source of truth for DV contract assets.

## Scope

This root contains:

- stage registries
- JSON schemas
- contract ADRs
- contract validation tools

## Canonical paths

- `contracts/registry/`
- `contracts/schemas/`
- `contracts/adr/`
- `contracts/tools/`

## Rules

1. New canonical contract assets must be created under this root.
2. Runtime consumers must resolve contract paths through the shared contract resolver.
3. Legacy paths such as `agent/contracts`, `shared/contracts`, and `eii_engine/contracts` must not be treated as source of truth.
4. Validation must pass through `contracts/tools/verify_contracts.py`.

## Current DV baseline commands

- `.\agent\dv.ps1 selftest`
- `.\agent\dv.ps1 newrun`
- `.\agent\dv.ps1 run <RUN_ID>`

## Lifecycle notes

- `newrun` creates a fresh run directory and initial `run.meta.json`
- `run <RUN_ID>` executes an existing run
- finalized runs are protected against overwrite

## Legacy surfaces

The old PowerShell toolchain is no longer the canonical operational path for DV baseline behavior.
Legacy surfaces remain only until they are explicitly deprecated or remapped.