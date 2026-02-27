# ps_toolkit.ps1 (PS5.1-safe, root-aware)
Set-StrictMode -Version Latest

# Repo root anchor (prefer global DV_ROOT set by dv.ps1 / DV.Toolkit.ps1)
if (-not (Get-Variable -Name DV_ROOT -Scope Script -ErrorAction SilentlyContinue)) {
  Set-Variable -Name DV_ROOT -Scope Script -Value $null -Force
}
if (-not $script:DV_ROOT -and $global:DV_ROOT) { $script:DV_ROOT = $global:DV_ROOT }
if (-not $script:DV_ROOT) { $script:DV_ROOT = (Get-Location).Path }

function Resolve-DVPath {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) { throw "Path is empty" }

  # If absolute, keep it
  if ([System.IO.Path]::IsPathRooted($Path)) { return $Path }

  # If relative, resolve against DV_ROOT (not CWD)
  return (Join-Path $script:DV_ROOT $Path)
}

function New-DirIfMissing {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Write-Utf8NoBom {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Content
  )

  $full = Resolve-DVPath -Path $Path
  $parent = Split-Path -Parent $full
  if ($parent) { New-DirIfMissing -Path $parent }

  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($full, $Content, $enc)
}

function Write-Artifact {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Content
  )
  Write-Utf8NoBom -Path $Path -Content $Content
}

Set-Alias -Name DV-WriteArtifact -Value Write-Artifact -ErrorAction SilentlyContinue