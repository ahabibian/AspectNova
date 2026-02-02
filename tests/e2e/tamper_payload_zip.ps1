# tests\e2e\tamper_payload_zip.ps1
# Tamper payload.zip by MODIFYING an entry inside the zip.
# Expect restore --verify-sha to detect sha_mismatch.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $repoRoot "tools"))) {
  throw "Run this from repo root (AspectNova). tools/ not found."
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$tmpRoot = Join-Path $repoRoot ".tmp_e2e_tamper_payload"
if (Test-Path $tmpRoot) { Remove-Item -Recurse -Force $tmpRoot }
New-Item -ItemType Directory -Path $tmpRoot | Out-Null

# sample files
New-Item -ItemType Directory -Path (Join-Path $tmpRoot "tmp") | Out-Null
Set-Content -Path (Join-Path $tmpRoot "tmp\old.log") -Value "hello log" -Encoding utf8
Set-Content -Path (Join-Path $tmpRoot "tmp\test.tmp") -Value "hello tmp" -Encoding utf8

# scan json (minimal)
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

# policy copy (do not touch repo policy)
$policyRepo = Join-Path $repoRoot "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
if (!(Test-Path $policyRepo)) { throw "policy not found: $policyRepo" }
$policyDir  = Join-Path $tmpRoot "policy"
New-Item -ItemType Directory -Path $policyDir | Out-Null
$policyPath = Join-Path $policyDir "cleanup_rules.archive_first.yaml"
Copy-Item $policyRepo $policyPath -Force

$outDir      = Join-Path $tmpRoot "out"
New-Item -ItemType Directory -Path $outDir | Out-Null
$targetsPath = Join-Path $outDir "cleanup_targets.json"
$execReport  = Join-Path $outDir "execution_report.json"

python tools\extract_cleanup_targets_v1_1.py `
  --scan $scanPath `
  --rules $policyPath `
  --out $targetsPath `
  --root $tmpRoot | Out-Null

if (!(Test-Path $targetsPath)) { throw "cleanup_targets.json not created" }

# approval secret (needed only if remove-original is used; keep anyway)
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
$env:ASPECTNOVA_APPROVAL_SECRET = [Convert]::ToBase64String($b)

$runId = "tamper_payload_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$wsId  = "ws_tamper_payload"

# archive (EXECUTE) so payload.zip is produced
python tools\execute_cleanup_plan_v1_1.py `
  --targets $targetsPath `
  --rules $policyPath `
  --root $tmpRoot `
  --workspace-id $wsId `
  --run-id $runId `
  --out-report $execReport `
  --remove-original `
  --execute `
  --confirm-secret $env:ASPECTNOVA_APPROVAL_SECRET | Out-Null

# locate payload.zip
$zipPath = Join-Path $tmpRoot (".aspectnova\archive\{0}\{1}\payload.zip" -f $wsId, $runId)
if (!(Test-Path $zipPath)) { throw "payload.zip missing at $zipPath" }

# ---- TAMPER: modify an entry INSIDE zip (tmp/old.log) ----
$entryName = "tmp/old.log"

$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Update)
try {
  $e = $zip.GetEntry($entryName)
  if ($null -eq $e) { throw "zip entry not found: $entryName" }

  # Remove + recreate entry with new bytes
  $e.Delete()

  $newEntry = $zip.CreateEntry($entryName)
  $stream = $newEntry.Open()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes("TAMPERED CONTENT " + (Get-Date).ToString("o"))
    $stream.Write($bytes, 0, $bytes.Length)
  } finally {
    $stream.Dispose()
  }
} finally {
  $zip.Dispose()
}

# restore with verify_sha (must detect mismatch)
$restoreReport = Join-Path $outDir ("restore_report.{0}.{1}.json" -f $wsId, $runId)

python tools\restore_archive_v1_1.py `
  --root $tmpRoot `
  --workspace-id $wsId `
  --run-id $runId `
  --out-report $restoreReport `
  --execute `
  --verify-sha | Out-Null

$rr = Get-Content $restoreReport -Raw | ConvertFrom-Json
$errors = 0
if ($rr.summary -and $rr.summary.errors) { $errors = [int]$rr.summary.errors }

$bad = @()
if ($rr.items) { $bad = @($rr.items | Where-Object { $_.status -ne "ok" -and $_.status -ne "restored" }) }
# NOTE: depending on restore script variant, statuses may be "ok"/"error" or "restored"/"failed".
# So detect either:
$failed = @()
if ($rr.items) { $failed = @($rr.items | Where-Object { $_.status -match "error|failed" -or $_.error }) }

if ($errors -gt 0 -or $failed.Count -gt 0) {
  Write-Host "TAMPER PAYLOAD ZIP OK (tampering detected)" -ForegroundColor Green
  exit 0
}

throw "Tamper payload zip test FAILED: restore did not report mismatch/errors"
