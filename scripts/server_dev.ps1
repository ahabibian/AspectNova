# scripts\server_dev.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "$env:USERPROFILE\OneDrive - Ericsson\Desktop\AspectNova"

if ([string]::IsNullOrWhiteSpace($env:ASPECTNOVA_APPROVAL_SECRET)) {
  throw "Set ASPECTNOVA_APPROVAL_SECRET in this session before running server_dev.ps1"
}

$env:ASPECTNOVA_ENV  = "dev"
$env:ASPECTNOVA_ROOT = (Get-Location).Path
$env:PYTHONPATH      = (Get-Location).Path

python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
