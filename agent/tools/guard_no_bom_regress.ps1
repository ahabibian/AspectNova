Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail([string]$Msg) {
  Write-Error $Msg
  exit 1
}

$root = Get-Location
$patterns = @(
  'Set' + '-Content\s+.*-Encoding\s+UTF8.*policies[\\/].*\.json',
  'Out' + '-File\s+.*-Encoding\s+UTF8.*policies[\\/].*\.json'
)

$targets = @()
$targets += Get-ChildItem -Path $root -Recurse -File -Include "*.ps1","*.psm1" -ErrorAction Stop | ForEach-Object { $_.FullName }

$hits = @()
foreach ($t in $targets) {
  foreach ($pat in $patterns) {
    $m = Select-String -Path $t -Pattern $pat -AllMatches -ErrorAction SilentlyContinue
    if ($m) { $hits += $m }
  }
}

if ($hits.Count -gt 0) {
  $hits | ForEach-Object {
    Write-Host ("HIT: " + $_.Path + ":" + $_.LineNumber + " -> " + $_.Line.Trim())
  }
  Fail "Forbidden UTF8 encoding write to policies/*.json detected. Use Write-TextUtf8NoBom instead."
}

Write-Host "OK: guard_no_bom_regress passed"
exit 0