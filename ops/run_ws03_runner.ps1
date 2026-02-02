param(
  [ValidateSet("safe","execute")]
  [string]$Mode = "safe",

  [switch]$DoRestore,

  [string]$RestoreRunId = ""
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"

Set-Location (Split-Path $PSScriptRoot -Parent)  # project root

function New-AspectNovaRunId {
  "run_" + (Get-Date -Format "yyyyMMdd'T'HHmmss") + "Z_" + ([guid]::NewGuid().ToString("N").Substring(0,8))
}

# --- Config (ws03) ---
$workspaceId = "ws03"
$scanPath    = "agent\runs\scan_workspace_03\scan_result.items.json"
$policyPath  = "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
$outDir      = "out"
$registry    = Join-Path $outDir "run_registry.ws03.jsonl"

Ensure-Dir $outDir

if (!(Test-Path $scanPath))    { throw "Missing scan file: $scanPath" }
if (!(Test-Path $policyPath))  { throw "Missing policy file: $policyPath" }
if (!(Test-Path "tools\extract_cleanup_targets_v1_1.py")) { throw "Missing extractor: tools\extract_cleanup_targets_v1_1.py" }
if (!(Test-Path "tools\execute_cleanup_plan_v1_1.py"))    { throw "Missing executor: tools\execute_cleanup_plan_v1_1.py" }
if ($DoRestore -and !(Test-Path "tools\restore_archive_v1_1.py")) { throw "Missing restore tool: tools\restore_archive_v1_1.py" }

$runId = New-AspectNovaRunId

$targetsOut = Join-Path $outDir ("cleanup_targets.ws03.{0}.json" -f $runId)
$execReport = Join-Path $outDir ("execution_report.ws03.{0}.json" -f $runId)

# --- Registry: extract started ---
Append-Jsonl $registry @{
  ts_utc       = (Get-Date).ToUniversalTime().ToString("o")
  kind         = "extract"
  workspace_id = $workspaceId
  run_id       = $runId
  scan_path    = $scanPath
  policy_path  = $policyPath
  out_targets  = $targetsOut
  status       = "started"
}

python tools\extract_cleanup_targets_v1_1.py `
  --scan $scanPath `
  --rules $policyPath `
  --out $targetsOut `
  --root "." `
  --derive-dirs-depth 8 `
  --fail-on-bad-delete-ext

$exitExtract = $LASTEXITCODE

Append-Jsonl $registry @{
  ts_utc       = (Get-Date).ToUniversalTime().ToString("o")
  kind         = "extract"
  workspace_id = $workspaceId
  run_id       = $runId
  out_targets  = $targetsOut
  exit_code    = $exitExtract
  status       = $(if ($exitExtract -eq 0) { "ok" } else { "failed" })
}

if ($exitExtract -ne 0) { throw "Extractor failed (EXITCODE=$exitExtract)" }

# --- Prepare executor flags ---
$execFlags = @(
  "--targets", $targetsOut,
  "--rules", $policyPath,
  "--root", ".",
  "--workspace-id", $workspaceId,
  "--run-id", $runId,
  "--out-report", $execReport
)

if ($Mode -eq "execute") {
  # generate secret if not set
  if (-not $env:ASPECTNOVA_APPROVAL_SECRET) {
    $b = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    $env:ASPECTNOVA_APPROVAL_SECRET = [Convert]::ToBase64String($b)
  }
  $execFlags += @("--remove-original","--execute","--confirm-secret",$env:ASPECTNOVA_APPROVAL_SECRET)
}

# --- Registry: archive started ---
Append-Jsonl $registry @{
  ts_utc       = (Get-Date).ToUniversalTime().ToString("o")
  kind         = "archive"
  workspace_id = $workspaceId
  run_id       = $runId
  targets_path = $targetsOut
  policy_path  = $policyPath
  report_path  = $execReport
  mode         = $Mode
  status       = "started"
}

python tools\execute_cleanup_plan_v1_1.py @execFlags
$exitArchive = $LASTEXITCODE

Append-Jsonl $registry @{
  ts_utc       = (Get-Date).ToUniversalTime().ToString("o")
  kind         = "archive"
  workspace_id = $workspaceId
  run_id       = $runId
  report_path  = $execReport
  exit_code    = $exitArchive
  status       = $(if ($exitArchive -eq 0) { "ok" } else { "failed" })
}

if ($exitArchive -ne 0) { throw "Archive failed (EXITCODE=$exitArchive). Check report: $execReport" }

Write-Host ("RUN_ID={0}" -f $runId)

# --- Optional restore ---
if ($DoRestore) {
  $rid = $RestoreRunId
  if ([string]::IsNullOrWhiteSpace($rid)) { $rid = $runId }

  $restoreId  = "restore_" + (Get-Date -Format "yyyyMMdd'T'HHmmss") + "Z"
  $restReport = Join-Path $outDir ("restore_report.ws03.{0}.json" -f $rid)

  Append-Jsonl $registry @{
    ts_utc       = (Get-Date).ToUniversalTime().ToString("o")
    kind         = "restore"
    workspace_id = $workspaceId
    run_id       = $rid
    restore_id   = $restoreId
    report_path  = $restReport
    status       = "started"
  }

  python tools\restore_archive_v1_1.py `
    --root "." `
    --workspace-id $workspaceId `
    --run-id $rid `
    --out-report $restReport `
    --execute `
    --verify-sha

  $exitRestore = $LASTEXITCODE

  Append-Jsonl $registry @{
    ts_utc       = (Get-Date).ToUniversalTime().ToString("o")
    kind         = "restore"
    workspace_id = $workspaceId
    run_id       = $rid
    restore_id   = $restoreId
    report_path  = $restReport
    exit_code    = $exitRestore
    status       = $(if ($exitRestore -eq 0) { "ok" } else { "failed" })
  }

  if ($exitRestore -ne 0) { throw "Restore failed (EXITCODE=$exitRestore). Check report: $restReport" }

  Write-Host ("RESTORED_RUN_ID={0}" -f $rid)
}

Write-Host "DONE"
exit 0
