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

$tmpRoot = Join-Path $repoRoot ".tmp_e2e_ws_full"
if (Test-Path $tmpRoot) { Remove-Item -Recurse -Force $tmpRoot }
New-Item -ItemType Directory -Path $tmpRoot | Out-Null

# Arrange
New-Item -ItemType Directory -Path (Join-Path $tmpRoot "tmp") | Out-Null
Set-Content -Path (Join-Path $tmpRoot "tmp\old.log") -Value "hello log" -Encoding utf8
Set-Content -Path (Join-Path $tmpRoot "tmp\test.tmp") -Value "hello tmp" -Encoding utf8

# Minimal scan_result.items.json for extractor v1.1
$scanPath = Join-Path $tmpRoot "scan_result.items.json"
$scanObj = @{
  schema_id      = "scan-result"
  schema_version = "v1.1"
  generated_at   = (Get-Date).ToUniversalTime().ToString("o")
  root           = $tmpRoot
  items          = @(
    @{ rel_path = "tmp/old.log";  size_bytes = (Get-Item (Join-Path $tmpRoot "tmp\old.log")).Length },
    @{ rel_path = "tmp/test.tmp"; size_bytes = (Get-Item (Join-Path $tmpRoot "tmp\test.tmp")).Length }
  )
}
$scanObj | ConvertTo-Json -Depth 12 | Set-Content -Path $scanPath -Encoding utf8

$policyPath  = Join-Path $repoRoot "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
$targetsDir  = Join-Path $tmpRoot "out"
$targetsPath = Join-Path $targetsDir "cleanup_targets.json"
$reportPath  = Join-Path $targetsDir "execution_report.json"
New-Item -ItemType Directory -Path $targetsDir | Out-Null

# Act 1: Extract
& python "tools\extract_cleanup_targets_v1_1.py" `
  --scan $scanPath `
  --rules $policyPath `
  --out $targetsPath `
  --root $tmpRoot | Out-Null

if ($LASTEXITCODE -ne 0) { throw "extractor failed exit=$LASTEXITCODE" }
if (!(Test-Path $targetsPath)) { throw "cleanup_targets.json not created" }

$targetsObj = Get-Content $targetsPath -Raw | ConvertFrom-Json
$byAction = $targetsObj.summary.by_action
Write-Host ("[OK] wrote {0} | targets={1} | by_action={2} | glob={3}" -f (Resolve-Path $targetsPath).Path, $targetsObj.summary.targets_total, ($byAction | ConvertTo-Json -Compress), $targetsObj.summary.matcher)

# Gate 1: must have >=2 ARCHIVE
$archiveTargets = @($targetsObj.targets | Where-Object { $_.action -eq "ARCHIVE" })
if ($archiveTargets.Count -lt 2) {
  Write-Host "Extractor produced insufficient ARCHIVE targets. Dumping cleanup_targets.json:" -ForegroundColor Yellow
  Write-Host (Get-Content $targetsPath -Raw)
  throw ("Expected >=2 ARCHIVE targets but got " + $archiveTargets.Count)
}

# Gate 2: decision_trace must exist on each target
$missingTrace = @($targetsObj.targets | Where-Object { -not $_.decision_trace })
if ($missingTrace.Count -gt 0) { throw ("Missing decision_trace on " + $missingTrace.Count + " targets") }

# Act 2: Execute archive
$runId = "e2e_full_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

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
if (!(Test-Path $reportPath)) { throw "execution_report.json missing" }

# Gate 3: report items have decision_trace and count >=2
$rep = Get-Content $reportPath -Raw | ConvertFrom-Json
$items = @($rep.items)
if ($items.Count -lt 2) { throw ("Expected >=2 report items but got " + $items.Count) }
$hasTrace = @($items | Where-Object { $_.decision_trace })
if ($hasTrace.Count -ne $items.Count) { throw ("execution_report items missing decision_trace: " + ($items.Count - $hasTrace.Count)) }

# Gate 4: trace_contract exists and has provenance_summary
$traceContract = Join-Path $tmpRoot (".aspectnova\contracts\ws_e2e\" + $runId + "\trace_contract.json")
if (!(Test-Path $traceContract)) { throw "trace_contract.json missing" }
$tc = Get-Content $traceContract -Raw | ConvertFrom-Json
if (-not $tc.provenance_summary) { throw "trace_contract.provenance_summary missing" }
if (-not $tc.provenance_summary.reason_counts) { throw "provenance_summary.reason_counts missing" }
if (-not $tc.provenance_summary.risk_bucket_counts) { throw "provenance_summary.risk_bucket_counts missing" }

# Gate 5: policy hash must match
$expected = python -c "from pathlib import Path; import hashlib; p=Path(r'$policyPath'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
if ($LASTEXITCODE -ne 0) { throw "failed to compute policy sha256" }
$actual = $tc.artifacts.policy_sha256
if ($expected.Trim() -ne ($actual + '').Trim()) { throw "POLICY HASH MISMATCH" }

# Gate 6: payload.zip exists
$zip = Join-Path $tmpRoot (".aspectnova\archive\ws_e2e\" + $runId + "\payload.zip")
if (!(Test-Path $zip)) { throw "payload.zip missing" }

# Sanity: originals removed
if (Test-Path (Join-Path $tmpRoot "tmp\old.log"))  { throw "old.log should have been removed" }
if (Test-Path (Join-Path $tmpRoot "tmp\test.tmp")) { throw "test.tmp should have been removed" }

Write-Host ("[OK] archive run complete | archived_ok=2 | payload={0}" -f (Resolve-Path $zip).Path) -ForegroundColor Green
Write-Host "E2E FULL (EXTRACTOR+EXECUTOR+GATE) ARCHIVE OK" -ForegroundColor Green
