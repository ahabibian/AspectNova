$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"

Set-Location (Split-Path $PSScriptRoot -Parent)  # project root

# --- Config (ws03) ---
$workspaceId = "ws03"
$policyPath  = "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
$targetsPath = "out\cleanup_targets.v4.balanced_3.ws03.v1_1.archive_first.json"
$outDir      = "out"
$registry    = Join-Path $outDir "run_registry.ws03.jsonl"

Ensure-Dir $outDir

# --- Preflight ---
if (!(Test-Path $policyPath))  { throw "Missing policy: $policyPath" }
if (!(Test-Path $targetsPath)) { throw "Missing targets: $targetsPath" }
if (!(Test-Path "tools\execute_cleanup_plan_v1_1.py")) { throw "Missing executor: tools\execute_cleanup_plan_v1_1.py" }

$runId = New-AspectNovaRunId
$env:ASPECTNOVA_APPROVAL_SECRET = New-AspectNovaSecret

$reportPath = Join-Path $outDir ("execution_report.{0}.{1}.json" -f $workspaceId, $runId)

# --- Registry: start ---
Append-Jsonl $registry @{
  ts_utc         = (Get-Date).ToUniversalTime().ToString("o")
  kind           = "archive"
  workspace_id   = $workspaceId
  run_id         = $runId
  policy_path    = $policyPath
  policy_sha256  = (Get-Sha256 $policyPath)
  targets_path   = $targetsPath
  targets_sha256 = (Get-Sha256 $targetsPath)
  report_path    = $reportPath
  status         = "started"
}

# --- Execute (DESTRUCTIVE gated in executor) ---
python tools\execute_cleanup_plan_v1_1.py `
  --targets $targetsPath `
  --rules $policyPath `
  --root "." `
  --workspace-id $workspaceId `
  --run-id $runId `
  --out-report $reportPath `
  --remove-original `
  --execute `
  --confirm-secret $env:ASPECTNOVA_APPROVAL_SECRET

$exit = $LASTEXITCODE

# --- Registry: finish ---
Append-Jsonl $registry @{
  ts_utc       = (Get-Date).ToUniversalTime().ToString("o")
  kind         = "archive"
  workspace_id = $workspaceId
  run_id       = $runId
  report_path  = $reportPath
  exit_code    = $exit
  status       = $(if ($exit -eq 0) { "ok" } else { "failed" })
}

Write-Host ("RUN_ID={0}" -f $runId)
Write-Host "DONE"
exit $exit
