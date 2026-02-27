param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]] $Args
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $here "agent\dv.ps1"

if (-not (Test-Path $target)) {
  throw "Missing agent dv.ps1: $target"
}

powershell -NoProfile -ExecutionPolicy Bypass -File $target @Args
exit $LASTEXITCODE