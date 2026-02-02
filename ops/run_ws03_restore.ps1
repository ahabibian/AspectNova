param(
  [Parameter(Mandatory=$true)]
  [string]$RunId,

  [switch]$VerifyProvenance,
  [switch]$StrictProvenance
)

$ErrorActionPreference = "Stop"

Set-Location "$env:USERPROFILE\OneDrive - Ericsson\Desktop\AspectNova"

$ws = "ws03"
Write-Host "RESTORE_FOR_RUN_ID=$RunId"

$argsList = @(
  "tools\restore_archive_v1_1.py",
  "--root", ".",
  "--workspace-id", $ws,
  "--run-id", $RunId,
  "--out-report", ("out\restore_report.{0}.{1}.json" -f $ws, $RunId),
  "--execute",
  "--verify-sha"
)

if ($VerifyProvenance) { $argsList += "--verify-provenance" }
if ($StrictProvenance) { $argsList += "--strict-provenance" }

python @argsList
Write-Host "DONE"
