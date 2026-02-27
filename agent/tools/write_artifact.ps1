function Write-Artifact {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Content,
    [string[]]$EnsureDirs = @(),
    [string[]]$EnsurePkgs = @(),
    [switch]$StripBom
  )

  foreach ($d in $EnsureDirs) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
  }

  foreach ($p in $EnsurePkgs) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
    $init = Join-Path $p "__init__.py"
    if (-not (Test-Path $init)) { [System.IO.File]::WriteAllText($init, "", (New-Object System.Text.UTF8Encoding($false))) }
  }

  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

  if ($StripBom) {
    $Content = $Content -replace "^\uFEFF",""
  }

  # Write UTF-8 بدون BOM
  [System.IO.File]::WriteAllText((Resolve-Path -LiteralPath $dir).Path + "\" + (Split-Path -Leaf $Path), $Content, [System.Text.UTF8Encoding]::new($false))
  Write-Host "WROTE $Path"
}
