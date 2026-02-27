Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail([string]$Msg) {
  Write-Error $Msg
  exit 1
}

function Has-Utf8Bom([string]$Path) {
  $b = [System.IO.File]::ReadAllBytes($Path)
  return ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
}

$root = Get-Location

# 1) BOM check for policies
$policyDir = Join-Path $root "policies"
if (-not (Test-Path $policyDir)) { Fail "Missing policies directory: $policyDir" }

$policyFiles = Get-ChildItem -Path $policyDir -Filter "*.json" -File -ErrorAction Stop
$bad = @()
foreach ($f in $policyFiles) {
  if (Has-Utf8Bom $f.FullName) { $bad += $f.FullName }
}
if ($bad.Count -gt 0) {
  Fail ("BOM detected in policy JSON files:`n" + ($bad -join "`n"))
}

# 2) Required pipeline files
$required = @(
  ".\run_pipeline.py",
  ".\run_manifest_stage.py",
  ".\tools\gate_manifest.py",
  ".\policies\manifest.policy.json",
  ".\stages\manifest\stage.py"
)
foreach ($r in $required) {
  if (-not (Test-Path $r)) { Fail "Missing required file: $r" }
}

# 3) Stage order check in run_pipeline.py
$src = Get-Content ".\run_pipeline.py" -Raw
$mi = $src.IndexOf("run_manifest_stage.py")
$ii = $src.IndexOf("run_integrity_stage.py")
if ($mi -lt 0) { Fail "run_manifest_stage.py not found in run_pipeline.py" }
if ($ii -lt 0) { Fail "run_integrity_stage.py not found in run_pipeline.py" }
if ($mi -gt $ii) { Fail "Stage order invalid: manifest must be before integrity" }

# 4) Guard against BOM regressions in scripts
$guardPath = ".\tools\guard_no_bom_regress.ps1"
if (-not (Test-Path $guardPath)) { Fail "Missing guard script: $guardPath" }

$rc = & powershell -NoProfile -ExecutionPolicy Bypass -File $guardPath
if ($LASTEXITCODE -ne 0) { Fail "Guard failed (see output above)" }
Write-Host "OK: lint_repo passed"
exit 0