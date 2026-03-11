param(
    [string]$RepoRoot = "C:\dev\AspectNova"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$env:ASPECTNOVA_CONTRACTS_ROOT = Join-Path $RepoRoot "contracts"
$env:PYTHONPATH = Join-Path $RepoRoot "agent\src"

Set-Location $RepoRoot

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content -Path $Path -Raw | ConvertFrom-Json)
}

Write-Host "== DV Integration Test ==" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot" -ForegroundColor DarkGray

# 1) Selftest
Write-Host "`n[1/4] selftest" -ForegroundColor Yellow
$selftestOutput = & powershell -ExecutionPolicy Bypass -File ".\agent\dv.ps1" selftest 2>&1
$selftestCode = $LASTEXITCODE
$selftestOutput | ForEach-Object { $_ }

if ($selftestCode -ne 0) {
    throw "Selftest failed with exit code $selftestCode"
}

# 2) New run
Write-Host "`n[2/4] newrun" -ForegroundColor Yellow
$newrunRaw = & powershell -ExecutionPolicy Bypass -File ".\agent\dv.ps1" newrun 2>&1
$newrunCode = $LASTEXITCODE
$newrunRaw | ForEach-Object { $_ }

if ($newrunCode -ne 0) {
    throw "newrun failed with exit code $newrunCode"
}

$newrunText = ($newrunRaw | Out-String).Trim()
$newrunJson = $newrunText | ConvertFrom-Json
$runId = $newrunJson.run_id

if (-not $runId) {
    throw "newrun did not return a run_id"
}

Write-Host "Created run: $runId" -ForegroundColor Green

# 3) Fresh run execute
Write-Host "`n[3/4] run fresh" -ForegroundColor Yellow
$runRaw = & powershell -ExecutionPolicy Bypass -File ".\agent\dv.ps1" run $runId 2>&1
$runCode = $LASTEXITCODE
$runRaw | ForEach-Object { $_ }

if ($runCode -ne 0) {
    throw "fresh run failed with exit code $runCode"
}

$metaPath = Join-Path $RepoRoot "runs\$runId\run.meta.json"
if (-not (Test-Path $metaPath)) {
    throw "run.meta.json missing after run: $metaPath"
}

$meta = Read-JsonFile -Path $metaPath
if ($meta.state -ne "finalized") {
    throw "Expected finalized state, got: $($meta.state)"
}
if ($meta.last_status -ne "PASS") {
    throw "Expected PASS last_status, got: $($meta.last_status)"
}

Write-Host "Fresh run finalized correctly." -ForegroundColor Green

# 4) Re-run must fail
Write-Host "`n[4/4] rerun finalized should fail" -ForegroundColor Yellow
$rerunRaw = & powershell -ExecutionPolicy Bypass -File ".\agent\dv.ps1" run $runId 2>&1
$rerunCode = $LASTEXITCODE
$rerunRaw | ForEach-Object { $_ }

$rerunText = ($rerunRaw | Out-String)
if ($rerunText -notmatch 'final_already_exists') {
    throw "Expected anti-overwrite failure containing 'final_already_exists'"
}

Write-Host "`nDV integration test PASSED." -ForegroundColor Green
Write-Host "Run used: $runId" -ForegroundColor Cyan