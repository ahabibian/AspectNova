param(
  [Parameter(Mandatory=$true, Position=0)]
  [ValidateSet("selftest","approve","run","newrun")]
  [string]$Cmd,

  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

switch ($Cmd) {
  "selftest" {
    python (Join-Path $PSScriptRoot "selftest.py") @Args
    exit $LASTEXITCODE
  }
  default {
    # fallback: route to python CLI if you use it for other commands
    python -m aspectnova_agent.cli $Cmd @Args
    exit $LASTEXITCODE
  }
}