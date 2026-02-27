# DV.Toolkit.ps1 (shim)
# Canonical dev import point for AspectNova / Data_Verdict toolchain.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$root  = Resolve-Path (Join-Path $here "..\..")
$tools = Join-Path $root "tools"

# Load core toolkits (if present)
$files = @(
  (Join-Path $tools "toolkit.ps1"),
  (Join-Path $tools "ps_toolkit.ps1"))

foreach ($f in $files) {
  if (Test-Path $f) { . $f }
}

# Optional: show loaded DV commands
Get-Command DV-* -ErrorAction SilentlyContinue | Out-Null