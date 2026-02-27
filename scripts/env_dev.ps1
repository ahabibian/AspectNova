param(
  [string]$HostIp = "127.0.0.1",
  [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "$env:USERPROFILE\OneDrive - Ericsson\Desktop\AspectNova"

# REQUIRED
$env:ASPECTNOVA_ENV  = "dev"
$env:ASPECTNOVA_ROOT = (Get-Location).Path

# REQUIRED: set the real secret (must match client)
if ([string]::IsNullOrWhiteSpace($env:ASPECTNOVA_APPROVAL_SECRET)) {
  throw "ASPECTNOVA_APPROVAL_SECRET is not set in this session."
}

# optional (module resolution)
$env:PYTHONPATH = (Get-Location).Path

python -m uvicorn api.main:app --host $HostIp --port $Port --reload
