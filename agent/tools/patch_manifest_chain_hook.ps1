param(
  [string]$RepoRoot = (Get-Location).Path,
  [string]$OutDirRelDefault = "out"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $RepoRoot "tools\toolkit.ps1")

$Path = Join-Path $RepoRoot "run_pipeline.py"
if (!(Test-Path $Path)) { throw "run_pipeline.py not found." }

# Inject out_dir + manifest_chain imports near the known anchor line
Patch-RegexOnce -Path $Path `
  -Pattern "(?m)^\s*raise FileNotFoundError\(f\"missing evidence dir: \{E\}\"\)\s*$" `
  -Replacement @"
    raise FileNotFoundError(f""missing evidence dir: {E}"")

    # --- Manifest Chain / Ledger (hardening) ---
    out_dir = os.environ.get('ASPECTNOVA_OUT_DIR', '$OutDirRelDefault')
    try:
        from agent.src.lib.manifest_chain import attach_chain_fields, finalize_manifest_chain
    except Exception:
        attach_chain_fields = None
        finalize_manifest_chain = None
"@

Write-Host "OK: manifest chain hook scaffold injected." -ForegroundColor Green
