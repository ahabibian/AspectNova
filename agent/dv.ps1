param(
  [Parameter(Mandatory=$true, Position=0)]
  [ValidateSet("selftest","approve","run","newrun")]
  [string]$Cmd,

  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root


$global:DV_ROOT = $root
# Load toolkit surface
. (Resolve-Path ".\tools\dev\DV.Toolkit.ps1") | Out-Null

# Delegate to internal dev entrypoint
& (Resolve-Path ".\tools\dev\dev.ps1") -Cmd $Cmd @Args