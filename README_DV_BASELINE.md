# AspectNova DV Stable Core Baseline v1

This document records the current stabilized DV baseline.

## Canonical DV operational path

- `contracts/`
- `contracts/tools/verify_contracts.py`
- `shared/contract_root.py`
- `agent/src/aspectnova_agent/cli.py`
- `agent/src/aspectnova_agent/pipeline_runner.py`
- `agent/dv.ps1`
- `scripts/dv_integration_test.ps1`

## Baseline commands

- `.\agent\dv.ps1 selftest`
- `.\agent\dv.ps1 newrun`
- `.\agent\dv.ps1 run <RUN_ID>`

## Verified lifecycle

- fresh run creation works
- fresh run execution works
- finalized run anti-overwrite protection works
- run state persistence works through `run.meta.json`

## Legacy / deprecated surfaces

The following are no longer the canonical DV baseline path:

- `agent/tools/dev/DV.Toolkit.ps1`
- `agent/tools/dev/dev.ps1`
- legacy contract roots under `agent/contracts`, `shared/contracts`, `eii_engine/contracts`

These legacy surfaces remain only for controlled transition and must not be treated as source of truth.

## Not yet canonical

- `approve` command
- clone/resume/rerun lifecycle extensions
- broader product surface and organization-facing hardening