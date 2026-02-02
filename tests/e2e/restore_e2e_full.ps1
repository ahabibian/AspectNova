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

$tmpRoot = Join-Path $repoRoot ".tmp_e2e_ws_restore"
if (Test-Path $tmpRoot) { Remove-Item -Recurse -Force $tmpRoot }
New-Item -ItemType Directory -Path $tmpRoot | Out-Null

# Arrange
New-Item -ItemType Directory -Path (Join-Path $tmpRoot "tmp") | Out-Null
Set-Content -Path (Join-Path $tmpRoot "tmp\old.log") -Value "hello log" -Encoding utf8
Set-Content -Path (Join-Path $tmpRoot "tmp\test.tmp") -Value "hello tmp" -Encoding utf8

# Build scan for extractor
$scanPath = Join-Path $tmpRoot "scan_result.items.json"
$scanObj = @{
  schema_id="scan-result"; schema_version="v1.1"; generated_at=(Get-Date).ToUniversalTime().ToString("o"); root=$tmpRoot
  items=@(
    @{ rel_path="tmp/old.log"; size_bytes=(Get-Item (Join-Path $tmpRoot "tmp\old.log")).Length },
    @{ rel_path="tmp/test.tmp"; size_bytes=(Get-Item (Join-Path $tmpRoot "tmp\test.tmp")).Length }
  )
}
$scanObj | ConvertTo-Json -Depth 12 | Set-Content -Path $scanPath -Encoding utf8

$policyPath  = Join-Path $repoRoot "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
$targetsDir  = Join-Path $tmpRoot "out"
New-Item -ItemType Directory -Path $targetsDir | Out-Null
$targetsPath = Join-Path $targetsDir "cleanup_targets.json"
$reportPath  = Join-Path $targetsDir "execution_report.json"

# Extract
& python "tools\extract_cleanup_targets_v1_1.py" --scan $scanPath --rules $policyPath --out $targetsPath --root $tmpRoot | Out-Null
if ($LASTEXITCODE -ne 0) { throw "extractor failed exit=$LASTEXITCODE" }

# Execute archive
$runId = "e2e_restore_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
$env:ASPECTNOVA_APPROVAL_SECRET = [Convert]::ToBase64String($b)

& python "tools\execute_cleanup_plan_v1_1.py" `
  --targets $targetsPath --rules $policyPath --root $tmpRoot `
  --workspace-id "ws_e2e" --run-id $runId --out-report $reportPath `
  --remove-original --execute --confirm-secret $env:ASPECTNOVA_APPROVAL_SECRET | Out-Null
if ($LASTEXITCODE -ne 0) { throw "executor failed exit=$LASTEXITCODE" }

# Restore
$restoreReport = Join-Path $targetsDir ("restore_report.ws_e2e." + $runId + ".json")
& python "tools\restore_archive_v1_1.py" `
  --root $tmpRoot `
  --workspace-id "ws_e2e" `
  --run-id $runId `
  --out-report $restoreReport `
  --execute `
  --verify-sha | Out-Null
if ($LASTEXITCODE -ne 0) { throw "restore failed exit=$LASTEXITCODE" }
if (!(Test-Path $restoreReport)) { throw "restore_report missing" }

# Gates
$d = Get-Content $restoreReport -Raw | ConvertFrom-Json
$items = @($d.items)
if ($items.Count -lt 2) { throw "Expected >=2 restore items but got $($items.Count)" }

foreach ($it in $items) {
  if ($it.status -ne "ok") { throw "restore item status != ok : $($it.rel_path)" }
  if ($it.expected_sha256 -ne $it.actual_sha256) { throw "sha mismatch for $($it.rel_path)" }
  $fp = Join-Path $tmpRoot ($it.rel_path -replace "/","\")
  if (!(Test-Path $fp)) { throw "restored file missing on disk: $fp" }
}

Write-Host ("[OK] restore complete | out={0} | ok={1} errors=0" -f (Resolve-Path $restoreReport).Path, $items.Count) -ForegroundColor Green
Write-Host "E2E RESTORE (ARCHIVE->RESTORE->VERIFY) OK" -ForegroundColor Green
