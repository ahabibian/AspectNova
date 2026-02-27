param(
  [Parameter(Mandatory=$true)][string]$Path
)
$parent = Split-Path -Parent $Path
if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }

$content = [Console]::In.ReadToEnd()
[System.IO.File]::WriteAllText($Path, $content, [System.Text.UTF8Encoding]::new($false))
Write-Host "WROTE $Path"
