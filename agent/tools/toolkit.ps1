Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Force -Path $Path | Out-Null }
}

function Write-TextUtf8NoBom([string]$Path, [string]$Content) {
  $p = Split-Path -Parent $Path
  if ($p) { Ensure-Dir $p }
  [System.IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding($false)))
  "WROTE (noBOM) $Path"
}

function Backup-File([string]$Path) {
  if (Test-Path $Path) {
    $bak = "$Path.bak_$(Get-Date -Format yyyyMMdd_HHmmss)"
    Copy-Item $Path $bak -Force
    "BACKUP $bak"
  }
}

function Patch-RegexOnce([string]$Path, [string]$Pattern, [string]$Replacement) {
  if (-not (Test-Path $Path)) { throw "missing: $Path" }
  Backup-File $Path
  $src = Get-Content $Path -Raw
  $patched = [regex]::Replace($src, $Pattern, $Replacement, 1)
  if ($patched -eq $src) { throw "patch did not apply: $Path" }
  Write-TextUtf8NoBom $Path $patched | Out-Null
  "PATCHED $Path"
}

# --- DV public command surface (stable) ---
function DV-SelfTest { SelfTest }
function DV-Approve  { Approve }
function DV-NewRunId { NewRunId }
function DV-PyCompileAll { PyCompileAll }

# Helpers
function DV-EnsureDir { param([string]$Path) Ensure-Dir $Path }
function DV-WriteTextUtf8NoBom { param([string]$Path,[string]$Content) Write-TextUtf8NoBom $Path $Content }
function DV-BackupFile { param([string]$Path) Backup-File $Path }
function DV-PatchRegexOnce { param([string]$Path,[string]$Pattern,[string]$Replacement) Patch-RegexOnce $Path $Pattern $Replacement }
