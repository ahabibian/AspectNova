param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$WorkspaceId = "ws_api",

  # اگر خالی باشد از ASPECTNOVA_ROOT می‌گیرد
  [string]$Root = "",

  # اگر خالی باشد از مسیرهای پیش‌فرض پروژه پر می‌شود
  [string]$ScanPath = "",
  [string]$RulesPath = "",

  # حالت امن: پیش‌فرض True
  [bool]$SafeMode = $true,

  # اجرای واقعی (تغییر فایل‌ها): پیش‌فرض False
  [bool]$Execute = $false,

  # اگر Execute=True شد، این مشخص می‌کند فایل اصلی حذف شود یا نه
  [bool]$RemoveOriginal = $false,

  # اگر Execute=True شد باید confirm_secret بدهی (همان secret)
  [string]$ConfirmSecret = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require($cond, $msg) {
  if (-not $cond) { throw $msg }
}

# Root resolution
if ([string]::IsNullOrWhiteSpace($Root)) {
  $Root = $env:ASPECTNOVA_ROOT
}
Require (-not [string]::IsNullOrWhiteSpace($Root)) "ASPECTNOVA_ROOT is not set and -Root is empty."
Require (Test-Path $Root) "Root path does not exist: $Root"

# Default Scan/Rules
if ([string]::IsNullOrWhiteSpace($ScanPath)) {
  $ScanPath = Join-Path $Root "sandbox_execute_test.scan.root.json"
}
if ([string]::IsNullOrWhiteSpace($RulesPath)) {
  $RulesPath = Join-Path $Root "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
}
Require (Test-Path $ScanPath) "scan_path not found: $ScanPath"
Require (Test-Path $RulesPath) "rules_path not found: $RulesPath"

# Secret
if ([string]::IsNullOrWhiteSpace($env:ASPECTNOVA_APPROVAL_SECRET)) {
  throw "Set ASPECTNOVA_APPROVAL_SECRET in this session before running."
}
$ApprovalSecret = $env:ASPECTNOVA_APPROVAL_SECRET

if ($Execute -and [string]::IsNullOrWhiteSpace($ConfirmSecret)) {
  # پیش‌فرض: همان secret
  $ConfirmSecret = $ApprovalSecret
}

Write-Host "[Client] BaseUrl=$BaseUrl"
Write-Host "[Client] WorkspaceId=$WorkspaceId"
Write-Host "[Client] Root=$Root"
Write-Host "[Client] ScanPath=$ScanPath"
Write-Host "[Client] RulesPath=$RulesPath"
Write-Host "[Client] SafeMode=$SafeMode Execute=$Execute RemoveOriginal=$RemoveOriginal"

# 1) Health
Invoke-RestMethod -Uri "$BaseUrl/health" | Out-Host

# 2) Create run
$run = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workspaces/$WorkspaceId/runs" -Body (@{} | ConvertTo-Json) -ContentType "application/json"
$rid = $run.run_id
Write-Host "`nRUN_ID=$rid`n"

# 3) Approve
$approveBody = @{ approval_secret = $ApprovalSecret } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workspaces/$WorkspaceId/jobs/$rid/approve" -Body $approveBody -ContentType "application/json" | Out-Host

# 4) Execute (safe or real)
$execBodyObj = @{
  scan_path       = $ScanPath
  rules_path      = $RulesPath
  root            = $Root
  safe_mode       = $SafeMode
  execute         = $Execute
  remove_original = $RemoveOriginal
  confirm_secret  = $ConfirmSecret
}
$execBody = $execBodyObj | ConvertTo-Json

try {
  Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workspaces/$WorkspaceId/jobs/$rid/execute" -Body $execBody -ContentType "application/json" | Out-Host
} catch {
  Write-Host "`n[ERROR] Execute call failed. Response:"
  if ($_.Exception.Response) {
    $r = $_.Exception.Response.GetResponseStream()
    $sr = New-Object System.IO.StreamReader($r)
    $sr.ReadToEnd() | Out-Host
  }
  throw
}

# 5) Poll job status
$maxPoll = 60
for ($i=1; $i -le $maxPoll; $i++) {
  Start-Sleep -Seconds 1
  $j = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/workspaces/$WorkspaceId/jobs/$rid"
  Write-Host "JOB_STATUS=$($j.status) (poll $i/$maxPoll)"
  if ($j.status -in @("completed","failed")) { break }
}

$j = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/workspaces/$WorkspaceId/jobs/$rid"
$j | ConvertTo-Json -Depth 20 | Out-Host

if ($j.status -ne "completed") {
  Write-Host "Job did not complete. Showing last stderr/stdout (if files exist)..."
  if ($j.logs -and $j.logs.stderr -and (Test-Path $j.logs.stderr)) { Get-Content $j.logs.stderr -Raw | Out-Host }
  if ($j.logs -and $j.logs.stdout -and (Test-Path $j.logs.stdout)) { Get-Content $j.logs.stdout -Raw | Out-Host }
  throw "Job status = $($j.status). Stop here."
}

Write-Host "`nOK. Job completed."
