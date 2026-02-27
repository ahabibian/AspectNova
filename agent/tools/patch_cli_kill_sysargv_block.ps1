param([string]$RepoRoot = (Get-Location).Path)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $RepoRoot "tools\toolkit.ps1")

$Path = Join-Path $RepoRoot "run_pipeline.py"
if (!(Test-Path $Path)) { throw "run_pipeline.py not found." }

# Ensure argparse import exists (safe append after imports)
try {
  Patch-RegexOnce -Path $Path -Pattern "(?m)^import argparse\s*$" -Replacement "import argparse"
} catch {
  Patch-RegexOnce -Path $Path -Pattern "(?s)^(import[^\r\n]*\r?\n)+" -Replacement "`$0import argparse`n"
}

# Insert build_args above main if missing
try {
  Patch-RegexOnce -Path $Path -Pattern "(?s)def build_args\(\):" -Replacement "def build_args():"
} catch {
  Patch-RegexOnce -Path $Path -Pattern "(?m)^(def main\()" -Replacement @"
def build_args():
    p = argparse.ArgumentParser()
    p.add_argument('--run-id', dest='run_id', required=True)
    p.add_argument('--runs-dir', dest='runs_dir', default='runs')
    return p.parse_args()

def main(
"@
}

# KILL a sys.argv parsing block (common pattern): from a line containing sys.argv up to next blank line
Patch-RegexOnce -Path $Path `
  -Pattern "(?s)^\s*.*sys\.argv.*\r?\n(?:^\s*.*\r?\n)*?(?:\r?\n)" `
  -Replacement @"
    # [HARDENED] argparse-based CLI
    args = build_args()
    run_id = args.run_id
    runs_dir = args.runs_dir

"@

# Fail if sys.argv still present
$src = Get-Content -Raw -Encoding UTF8 $Path
if ($src -match "sys\.argv") { throw "HARD FAIL: sys.argv still present after patch. Paste Select-String sys.argv context." }

Write-Host "OK: sys.argv parsing removed, argparse enforced." -ForegroundColor Green
