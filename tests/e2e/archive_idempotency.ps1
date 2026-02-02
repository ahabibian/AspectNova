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

$tmpRoot = Join-Path $repoRoot ".tmp_e2e_ws_idem"
if (Test-Path $tmpRoot) { Remove-Item -Recurse -Force $tmpRoot }
New-Item -ItemType Directory -Path $tmpRoot | Out-Null

New-Item -ItemType Directory -Path (Join-Path $tmpRoot "tmp") | Out-Null
Set-Content -Path (Join-Path $tmpRoot "tmp\old.log") -Value "hello log" -Encoding utf8
Set-Content -Path (Join-Path $tmpRoot "tmp\test.tmp") -Value "hello tmp" -Encoding utf8

# Minimal targets
$targetsDir  = Join-Path $tmpRoot "out"
New-Item -ItemType Directory -Path $targetsDir | Out-Null
$targetsPath = Join-Path $targetsDir "cleanup_targets.json"

$targetsObj = @{
  schema_id="cleanup-targets"; schema_version="v1.1"; generated_at=(Get-Date).ToUniversalTime().ToString("o"); root=$tmpRoot
  inputs=@{ scan_path=$null; policy_path=$null }
  summary=@{ targets_total=2; by_action=@{ DELETE=0; ARCHIVE=2; MOVE=0; NOOP=0 }; matcher="manual" }
  targets=@(
    @{ action="ARCHIVE"; rel_path="tmp/old.log"; path="tmp/old.log"; ext=".log"; size_bytes=1; matched_rule="junk.delete.temp_logs.allowed_scopes"; decision_trace=@{ matcher="manual"; matched_rule="junk.delete.temp_logs.allowed_scopes"; reason_codes=@("junk.delete.temp_logs.allowed_scopes"); risk_bucket="B" } },
    @{ action="ARCHIVE"; rel_path="tmp/test.tmp"; path="tmp/test.tmp"; ext=".tmp"; size_bytes=1; matched_rule="junk.delete.temp_logs.allowed_scopes"; decision_trace=@{ matcher="manual"; matched_rule="junk.delete.temp_logs.allowed_scopes"; reason_codes=@("junk.delete.temp_logs.allowed_scopes"); risk_bucket="B" } }
  )
}
$targetsObj | ConvertTo-Json -Depth 20 | Set-Content -Path $targetsPath -Encoding utf8

$policyPath = Join-Path $repoRoot "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
$runId = "run_same"
$report1 = Join-Path $targetsDir "execution_report.run1.json"
$report2 = Join-Path $targetsDir "execution_report.run2.json"

# approval secret
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
$env:ASPECTNOVA_APPROVAL_SECRET = [Convert]::ToBase64String($b)

# Run 1 (should succeed)
& python "tools\execute_cleanup_plan_v1_1.py" `
  --targets $targetsPath --rules $policyPath --root $tmpRoot `
  --workspace-id "ws_idem" --run-id $runId --out-report $report1 `
  --remove-original --execute --confirm-secret $env:ASPECTNOVA_APPROVAL_SECRET | Out-Null

if ($LASTEXITCODE -ne 0) { throw "Run1 failed unexpectedly (EXITCODE=$LASTEXITCODE)" }
$zip = Join-Path $tmpRoot (".aspectnova\archive\ws_idem\" + $runId + "\payload.zip")
if (!(Test-Path $zip)) { throw "payload.zip missing after run1" }
Write-Host ("[OK] archive run complete | archived_ok=2 | payload={0}" -f (Resolve-Path $zip).Path) -ForegroundColor Green

# Run 2 (MUST fail)
& python "tools\execute_cleanup_plan_v1_1.py" `
  --targets $targetsPath --rules $policyPath --root $tmpRoot `
  --workspace-id "ws_idem" --run-id $runId --out-report $report2 `
  --remove-original --execute --confirm-secret $env:ASPECTNOVA_APPROVAL_SECRET | Out-Null

if ($LASTEXITCODE -eq 0) { throw "Run2 should have failed but succeeded (idempotency broken)" }
Write-Host "run_id_already_exists" -ForegroundColor Yellow
Write-Host "IDEMPOTENCY OK (second run failed as expected)" -ForegroundColor Green
