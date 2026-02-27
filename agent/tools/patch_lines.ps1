param(
  [Parameter(Mandatory=$true)][string]$Path,
  [Parameter(Mandatory=$true)][int]$StartLine,
  [Parameter(Mandatory=$true)][int]$EndLine,
  [Parameter(Mandatory=$true)][string]$InsertText
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (!(Test-Path $Path)) { throw "File not found: $Path" }
if ($StartLine -lt 1 -or $EndLine -lt $StartLine) { throw "Invalid line range: $StartLine..$EndLine" }

$lines = Get-Content -Path $Path -Encoding UTF8
$lineCount = $lines.Count
if ($EndLine -gt $lineCount) { throw "EndLine $EndLine exceeds file length $lineCount" }

# 1-based to 0-based
$before = @()
if ($StartLine -gt 1) { $before = $lines[0..($StartLine-2)] }

$after = @()
if ($EndLine -lt $lineCount) { $after = $lines[($EndLine)..($lineCount-1)] }

$insertLines = $InsertText -split "`n"
$newLines = @()
$newLines += $before
$newLines += $insertLines
$newLines += $after

# Write UTF-8 NO BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines((Resolve-Path $Path), $newLines, $utf8NoBom)

Write-Host "PATCH_LINES OK: $Path lines $StartLine..$EndLine replaced" -ForegroundColor Green
