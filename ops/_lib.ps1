$ErrorActionPreference = "Stop"

function New-AspectNovaRunId {
  "run_" + (Get-Date -Format "yyyyMMdd'T'HHmmss") + "Z_" + ([guid]::NewGuid().ToString("N").Substring(0,8))
}

function New-AspectNovaSecret {
  $b = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  [Convert]::ToBase64String($b)
}

function Ensure-Dir([string]$Path) {
  if (!(Test-Path $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

function Write-Utf8NoBom([string]$Path, [string]$Text) {
  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

function Append-Jsonl([string]$Path, [hashtable]$Obj) {
  Ensure-Dir (Split-Path $Path)
  $line = ($Obj | ConvertTo-Json -Depth 20 -Compress)
  Add-Content -Path $Path -Value $line -Encoding UTF8
}

function Get-Sha256([string]$Path) {
  if (!(Test-Path $Path)) { return $null }
  (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLower()
}
