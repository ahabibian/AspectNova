Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Has-Utf8Bom([string]$Path) {
  $b = [System.IO.File]::ReadAllBytes($Path)
  return ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
}

$root = Get-Location
$policyDir = Join-Path $root "policies"
if (-not (Test-Path $policyDir)) { throw "Missing policies directory: $policyDir" }

$policyFiles = Get-ChildItem -Path $policyDir -Filter "*.json" -File -ErrorAction Stop

$fixed = 0
foreach ($f in $policyFiles) {
  if (Has-Utf8Bom $f.FullName) {
    $txt = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
    [System.IO.File]::WriteAllText($f.FullName, $txt, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host ("FIXED BOM: " + $f.FullName)
    $fixed++
  }
}

Write-Host ("DONE. Files fixed: " + $fixed)