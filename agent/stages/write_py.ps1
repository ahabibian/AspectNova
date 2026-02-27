@'
param(
  [Parameter(Mandatory=$true)][string]$Path
)
$dest = Resolve-Path -LiteralPath (Split-Path -Parent $Path) -ErrorAction SilentlyContinue
if (-not $dest) { New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null }

# Read everything from STDIN and write as UTF-8
$content = [Console]::In.ReadToEnd()
[System.IO.File]::WriteAllText($Path, $content, [System.Text.UTF8Encoding]::new($false))
Write-Host "WROTE $Path"
'@ | Set-Content -Encoding UTF8 .\tools\write_py.ps1
