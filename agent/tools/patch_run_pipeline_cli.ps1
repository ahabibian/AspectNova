param([string]$RepoRoot = (Get-Location).Path)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $RepoRoot "tools\toolkit.ps1")

$Path = Join-Path $RepoRoot "run_pipeline.py"
if (!(Test-Path $Path)) { throw "run_pipeline.py not found." }

# Anchor-based patching only (your file contains sys.argv and missing evidence dir)

# (A) ensure argparse import exists (add after other imports if not present)
try {
  Patch-RegexOnce -Path $Path `
    -Pattern "(?m)^import sys\s*$" `
    -Replacement "import sys`nimport argparse"
} catch {
  # fallback: add argparse near the top if import sys not found exactly
  Patch-RegexOnce -Path $Path `
    -Pattern "(?s)^(.*?)(\r?\n\r?\n)" `
    -Replacement "`$1`nimport argparse`n`n`$2"
}

# (B) add build_args() right before def main
Patch-RegexOnce -Path $Path `
  -Pattern "(?m)^(def main\()" `
  -Replacement @"
def build_args():
    p = argparse.ArgumentParser()
    p.add_argument('--run-id', dest='run_id', required=True)
    p.add_argument('--runs-dir', dest='runs_dir', default='runs')
    return p.parse_args()

def main(
"@

# (C) inside main(): force args usage before first evidence-dir usage
Patch-RegexOnce -Path $Path `
  -Pattern "(?s)(def main\([^)]*\):\r?\n)" `
  -Replacement @"
`$1    args = build_args()
    run_id = args.run_id
    runs_dir = args.runs_dir

"@

Write-Host "OK: run_pipeline.py patched for argparse (--run-id, --runs-dir)." -ForegroundColor Green
