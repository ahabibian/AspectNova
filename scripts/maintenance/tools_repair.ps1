Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Run this from repo root: ...\AspectNova
$repoRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $repoRoot "tools"))) {
  throw "Run this from the repo root (AspectNova). 'tools' folder not found."
}

Write-Host "Repairing tools + policy from embedded known-good copies..." -ForegroundColor Cyan

# Timestamp for backups
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

function Restore-FileFromBase64 {
  param(
    [Parameter(Mandatory=$true)][string]$RelPath,
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$B64
  )

  $dest = Join-Path $repoRoot $RelPath
  $bak  = $dest + ".bak." + $ts

  if (Test-Path $dest) { Copy-Item $dest $bak -Force }

  # Remove whitespace/newlines safely
  $b64_clean = ($B64 -replace "\s","")
  [IO.File]::WriteAllBytes($dest, [Convert]::FromBase64String($b64_clean))

  Write-Host ("OK restored: {0} -> {1}" -f $Name, $RelPath) -ForegroundColor Green
}

# -------------------------
# Embedded files (Base64)
# -------------------------

$B64_EXTRACTOR = @'
<BASE64_EXTRACTOR_WILL_BE_INSERTED_HERE>
'@

$B64_EXECUTOR = @'
<BASE64_EXECUTOR_WILL_BE_INSERTED_HERE>
'@

$B64_RESTORE = @'
<BASE64_RESTORE_WILL_BE_INSERTED_HERE>
'@

$B64_POLICY = @'
<BASE64_POLICY_WILL_BE_INSERTED_HERE>
'@

# -------------------------
# Restore files
# -------------------------
Restore-FileFromBase64 -RelPath "tools\extract_cleanup_targets_v1_1.py" -Name "extract_cleanup_targets_v1_1.py" -B64 $B64_EXTRACTOR
Restore-FileFromBase64 -RelPath "tools\execute_cleanup_plan_v1_1.py"    -Name "execute_cleanup_plan_v1_1.py"    -B64 $B64_EXECUTOR
Restore-FileFromBase64 -RelPath "tools\restore_archive_v1_1.py"         -Name "restore_archive_v1_1.py"         -B64 $B64_RESTORE
Restore-FileFromBase64 -RelPath "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml" -Name "cleanup_rules.v4.balanced_3.archive_first.yaml" -B64 $B64_POLICY

Write-Host "`nOK: files restored. Quick sanity checks:" -ForegroundColor Green
python tools\extract_cleanup_targets_v1_1.py --help | Out-Host
python tools\execute_cleanup_plan_v1_1.py --help | Out-Host
python tools\restore_archive_v1_1.py --help | Out-Host

Write-Host "`nNow re-run tests:" -ForegroundColor Yellow
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File tests\e2e\archive_e2e.ps1" -ForegroundColor Yellow
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File tests\e2e\archive_e2e_full.ps1" -ForegroundColor Yellow
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File tests\e2e\archive_idempotency.ps1" -ForegroundColor Yellow
