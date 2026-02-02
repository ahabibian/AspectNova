# Agent - File Scanner (Schema-first)

This project scans a directory tree and produces:
- `output/scan_result.json` (raw)
- `output/scan_result.canonical.json` (canonical)

Both outputs are validated against `src/agent/schemas/scan_result.schema.v1.json` (strict JSON Schema v1).

## Install (Windows)
```bat
python -m pip install -e .
python -m pip install -U pytest

