# tests\e2e\tamper_policy_hash.ps1
# Tamper the POLICY COPY used for the run (in tmpRoot) and ensure mismatch vs trace_contract

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Run from repo root (AspectNova)
$repoRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $repoRoot "tools"))) {
  throw "Run this from repo root (AspectNova). tools/ not found."
}

$tmpRoot = Join-Path $repoRoot ".tmp_e2e_tamper_policy"
if (Test-Path $tmpRoot) { Remove-Item -Recurse -Force $tmpRoot }
New-Item -ItemType Directory -Path $tmpRoot | Out-Null

# sample files
New-Item -ItemType Directory -Path (Join-Path $tmpRoot "tmp") | Out-Null
Set-Content -Path (Join-Path $tmpRoot "tmp\old.log") -Value "hello log" -Encoding utf8
Set-Content -Path (Join-Path $tmpRoot "tmp\test.tmp") -Value "hello tmp" -Encoding utf8

# scan json
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

# IMPORTANT: use a COPY of policy inside tmpRoot (do not mutate repo file)
$policyRepo = Join-Path $repoRoot "shared\policy\cleanup_rules.v4.balanced_3.archive_first.yaml"
if (!(Test-Path $policyRepo)) { throw "policy not found: $policyRepo" }

$policyDir  = Join-Path $tmpRoot "policy"
New-Item -ItemType Directory -Path $policyDir | Out-Null
$policyPath = Join-Path $policyDir "cleanup_rules.archive_first.yaml"
Copy-Item $policyRepo $policyPath -Force

$outDir      = Join-Path $tmpRoot "out"
New-Item -ItemType Directory -Path $outDir | Out-Null
$targetsPath = Join-Path $outDir "cleanup_targets.json"
$reportPath  = Join-Path $outDir "execution_report.json"

python tools\extract_cleanup_targets_v1_1.py `
  --scan $scanPath `
  --rules $policyPath `
  --out $targetsPath `
  --root $tmpRoot | Out-Null

if (!(Test-Path $targetsPath)) { throw "cleanup_targets.json not created" }

# approval secret
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
$env:ASPECTNOVA_APPROVAL_SECRET = [Convert]::ToBase64String($b)

$runId = "tamper_policy_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$wsId  = "ws_tamper"

python tools\execute_cleanup_plan_v1_1.py `
  --targets $targetsPath `
  --rules $policyPath `
  --root $tmpRoot `
  --workspace-id $wsId `
  --run-id $runId `
  --out-report $reportPath `
  --remove-original `
  --execute `
  --confirm-secret $env:ASPECTNOVA_APPROVAL_SECRET | Out-Null

# read trace_contract
$tracePath = Join-Path $tmpRoot (".aspectnova\contracts\{0}\{1}\trace_contract.json" -f $wsId, $runId)
if (!(Test-Path $tracePath)) { throw "trace_contract.json missing at $tracePath" }

$tc = Get-Content $tracePath -Raw | ConvertFrom-Json
$recorded = $tc.artifacts.policy_sha256
if (-not $recorded) { throw "trace_contract missing artifacts.policy_sha256" }

# Tamper the POLICY COPY used for the run
Add-Content -Path $policyPath -Value "`n# tamper_policy_test $(Get-Date -Format o)" -Encoding utf8

# Compute sha of tampered policy copy
$actual = python -c "from pathlib import Path; import hashlib; p=Path(r'$policyPath'); print(hashlib.sha256(p.read_bytes()).hexdigest())"

if ($actual -ne $recorded) {
  Write-Host "TAMPER POLICY HASH OK (mismatch detected as expected)" -ForegroundColor Green
  exit 0
}

throw "Tamper policy test FAILED: hash still matches after modification (unexpected)"
