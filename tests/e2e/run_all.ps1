Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  if ($PSScriptRoot -and $PSScriptRoot.Trim().Length -gt 0) {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
  }
  return (Get-Location).Path
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$tests = @(
  "tests\e2e\toolchain_integrity.ps1",
  "tests\e2e\archive_e2e.ps1",
  "tests\e2e\archive_e2e_full.ps1",
  "tests\e2e\restore_e2e_full.ps1",
  "tests\e2e\archive_idempotency.ps1"
)

foreach ($t in $tests) {
  Write-Host "`n===============================" -ForegroundColor DarkGray
  Write-Host "[RUN] $t" -ForegroundColor Cyan
  & powershell -NoProfile -ExecutionPolicy Bypass -File $t
  if ($LASTEXITCODE -ne 0) { throw "FAILED: $t (exit=$LASTEXITCODE)" }
}

Write-Host "`nALL E2E TESTS PASSED ✅" -ForegroundColor Green
