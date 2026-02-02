Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  if ($PSScriptRoot -and $PSScriptRoot.Trim().Length -gt 0) {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
  }
  # Fallback when pasted line-by-line in console
  return (Get-Location).Path
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$tools = @(
  "tools\extract_cleanup_targets_v1_1.py",
  "tools\execute_cleanup_plan_v1_1.py",
  "tools\restore_archive_v1_1.py"
)

Write-Host "[TEST] toolchain_integrity: checking tools exist + not placeholder + runnable ..." -ForegroundColor Cyan

foreach ($t in $tools) {
  $p = Join-Path $repoRoot $t
  if (!(Test-Path $p)) { throw "Missing tool file: $t" }

  $head = Get-Content $p -TotalCount 5 -ErrorAction Stop | Out-String
  if ($head -match "<PASTE_|<REPLACE_WITH_|<BASE64_") {
    throw "Tool file looks like placeholder (broken): $t"
  }

  & python $p --help *> $null
  if ($LASTEXITCODE -ne 0) { throw "Tool '--help' failed: $t (exit=$LASTEXITCODE)" }
  Write-Host "  OK: $t" -ForegroundColor Green
}

Write-Host "TOOLCHAIN INTEGRITY OK" -ForegroundColor Green
