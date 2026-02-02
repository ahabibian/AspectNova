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

# Temp workspace root
$tmpRoot = Join-Path $repoRoot ".tmp_e2e_ws"
if (Test-Path $tmpRoot) { Remove-Item -Recurse -Force $tmpRoot }
New-Item -ItemType Directory -Path $tmpRoot | Out-Null

# Arrange: sample files
New-Item -ItemType Directory -Path (Join-Path $tmpRoot "tmp") | Out-Null
Set-Content -Path (Join-Path $tmpRoot "tmp\old.log") -Value "hello log" -Encoding utf8
Set-Content -Path (Join-Path $tmpRoot "tmp\test.tmp") -Value "hello tmp" -Encoding utf8

# Minimal targets file (bypass extractor)
$targetsDir  = Join-Path $tmpRoot "out"
New-Item -ItemType Directory -Path $targetsDir | Out-Null
$targetsPath = Join-Path $targetsDir "cleanup_targets.json"

$targetsObj = @{
  schema_id      = "cleanup-targets"
  schema_version = "v1.1"
  generated_at   = (Get-Date).ToUniversalTime().ToString("o")
  root           = $tmpRoot
  inputs         = @{
    scan_path   = $null
    policy_path = $null
  }
  summary        = @{
    targets_total = 2
    by_action     = @{ DELETE=0; ARCHIVE=2; MOVE=0; NOOP=0 }
    matcher       = "manual"
  }
  targets        = @(
    @{
      action="ARCHIVE"; rel_path="tmp/old.log"; path="tmp/old.log"; ext=".log"; size_bytes=(Get-Item (Join-Path $tmpRoot "tmp\old.log")).Length
      matched_rule="junk.delete.temp_logs.allowed_scopes"
      decision_trace=@{ matcher="manual"; matched_rule="junk.delete.temp_logs.allowed_scopes"; reason_codes=@("junk.delete.temp_logs.allowed_scopes"); risk_bucket="B" }
    },
    @{
      action="ARCHIVE"; rel_path="tmp/test.tmp"; path="tmp/test.tmp"; ext=".tmp"; size_bytes=(Get-Item (Join-Path $tmpRoot "tmp\test.tmp")).Length
      matched_rule="junk.delete.temp_logs.allowed_scopes"
      decision_trace=@{ matcher="manual"; matched_rule="junk.delete.temp_logs.allowed_scopes"; reason_codes=@("junk.delete.temp_logs.allowed_scopes"); risk_bucket="B" }
    }
  )
}

$targetsObj | ConvertTo-Json -Depth 20 | Set-Content -Path $targetsPath -Encoding utf8

# Execute archive
$policyPath = Join-Path $repoRoot "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
$reportPath = Join-Path $targetsDir "execution_report.json"
$runId = "e2e_safe_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

# Approval secret
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
$env:ASPECTNOVA_APPROVAL_SECRET = [Convert]::ToBase64String($b)

& python "tools\execute_cleanup_plan_v1_1.py" `
  --targets $targetsPath `
  --rules $policyPath `
  --root $tmpRoot `
  --workspace-id "ws_e2e" `
  --run-id $runId `
  --out-report $reportPath `
  --remove-original `
  --execute `
  --confirm-secret $env:ASPECTNOVA_APPROVAL_SECRET | Out-Null

if ($LASTEXITCODE -ne 0) { throw "executor failed exit=$LASTEXITCODE" }
if (!(Test-Path $reportPath)) { throw "execution_report missing: $reportPath" }

# Gate: payload.zip must exist
$zip = Join-Path $tmpRoot (".aspectnova\archive\ws_e2e\" + $runId + "\payload.zip")
if (!(Test-Path $zip)) { throw "payload.zip missing" }

Write-Host ("[OK] archive run complete | archived_ok=2 | payload={0}" -f (Resolve-Path $zip).Path) -ForegroundColor Green
Write-Host "E2E SAFE ARCHIVE OK" -ForegroundColor Green
