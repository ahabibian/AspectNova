param(
  [Parameter(Position=0)]
  [string] $Command = "",
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]] $Args
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$agentDv = Join-Path $here "agent\dv.ps1"

function _Run([string]$label, [scriptblock]$sb) {
  Write-Host "== $label =="
  & $sb
  $code = $LASTEXITCODE
  if ($code -ne 0) {
    Write-Host "FAIL: $label (exit=$code)"
    exit $code
  }
}

if (-not (Test-Path $agentDv)) {
  throw "Missing agent dv.ps1: $agentDv"
}

if ($Command -eq "gate") {
  # 1) selftest (includes strip_bom + devguard in current implementation)
  _Run "DV SELFTEST" { powershell -NoProfile -ExecutionPolicy Bypass -File $agentDv selftest }

  # 2) devguard explicit (defense-in-depth)
  _Run "DEVGUARD" { python (Join-Path $here "agent\tools\dev\devguard.py") }

  # 3) compileall (syntax/import sanity)
  _Run "PY COMPILEALL agent/src" { python -m compileall (Join-Path $here "agent\src") -q }
  if (Test-Path (Join-Path $here "api"))  { _Run "PY COMPILEALL api"  { python -m compileall (Join-Path $here "api") -q } }
  if (Test-Path (Join-Path $here "core")) { _Run "PY COMPILEALL core" { python -m compileall (Join-Path $here "core") -q } }

  Write-Host "GATE: OK"
  exit 0
}

# default: forward to canonical agent dv.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File $agentDv $Command @Args
exit $LASTEXITCODE