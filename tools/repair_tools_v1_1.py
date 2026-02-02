Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Always run from repo root
$repoRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $repoRoot "tools"))) {
  throw "Run this from the repo root (AspectNova). 'tools' folder not found."
}

# --- extract_cleanup_targets_v1_1.py ---
@'
<REPLACE_WITH_EXTRACTOR_CODE_FROM_THIS_MESSAGE>
'@ | Set-Content -Path "tools\extract_cleanup_targets_v1_1.py" -Encoding utf8 -NoNewline

# --- execute_cleanup_plan_v1_1.py ---
@'
<REPLACE_WITH_EXECUTOR_CODE_FROM_THIS_MESSAGE>
'@ | Set-Content -Path "tools\execute_cleanup_plan_v1_1.py" -Encoding utf8 -NoNewline

# --- restore_archive_v1_1.py ---
@'
<REPLACE_WITH_RESTORE_CODE_FROM_THIS_MESSAGE>
'@ | Set-Content -Path "tools\restore_archive_v1_1.py" -Encoding utf8 -NoNewline

Write-Host "OK: tools restored." -ForegroundColor Green
python tools\extract_cleanup_targets_v1_1.py --help | Out-Host
python tools\execute_cleanup_plan_v1_1.py --help | Out-Host
python tools\restore_archive_v1_1.py --help | Out-Host
