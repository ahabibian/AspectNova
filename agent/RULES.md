# AspectNova Repo Rules (Non-negotiable)

## Encoding
- All JSON policy/config files MUST be written as UTF-8 without BOM.
- Do NOT use: `Set-Content -Encoding UTF8` for JSON (it may write BOM).
- Use the toolkit function: `Write-TextUtf8NoBom`.

## Patching
- Never hand-edit generated artifacts under runs/.
- Any code/config patch MUST:
  1) create an automatic backup
  2) apply exactly once
  3) fail fast if pattern mismatch
- Use: `Patch-RegexOnce`.

## Pipeline stability
- `run_manifest_stage.py` must run immediately before integrity.
- Integrity must hash only stable allowlisted artifacts (manifest-driven).

## Verify before commit
- Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\lint_repo.ps1`
- Then run: `python .\run_pipeline.py <run_id>`