param(
  [switch]$WhatIfOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Safe cache cleanup only (non-destructive to source/contracts/archive)
# Removes: __pycache__, .pytest_cache, .mypy_cache, and *.pyc

$root = (Get-Location).Path

Write-Host "Root: $root"

$cacheDirs = @("__pycache__", ".pytest_cache", ".mypy_cache")

# Preview
Write-Host "`n[Preview] Cache directories:"
$dirs = Get-ChildItem -Recurse -Directory -Force -ErrorAction SilentlyContinue |
  Where-Object { $cacheDirs -contains $_.Name }

$dirs | Select-Object FullName | Format-Table -AutoSize | Out-Host

Write-Host "`n[Preview] .pyc files:"
$pyc = Get-ChildItem -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -eq ".pyc" }

$pyc | Select-Object FullName, Length | Format-Table -AutoSize | Out-Host

if ($WhatIfOnly) {
  Write-Host "`nWhatIfOnly enabled. No deletions performed."
  exit 0
}

# Delete
Write-Host "`n[Delete] Removing cache directories..."
$dirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[Delete] Removing .pyc files..."
$pyc | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "`nDone."
