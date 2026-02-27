param([string]$RepoRoot = (Get-Location).Path)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $RepoRoot "tools\toolkit.ps1")

$Path = Join-Path $RepoRoot "run_pipeline.py"
if (!(Test-Path $Path)) { throw "run_pipeline.py not found." }

# 0) Ensure argparse import exists somewhere
try {
  Patch-RegexOnce -Path $Path -Pattern "(?m)^import argparse\s*$" -Replacement "import argparse"
} catch {
  # add after first import block (safe)
  Patch-RegexOnce -Path $Path `
    -Pattern "(?s)^(import[^\r\n]*\r?\n)+" `
    -Replacement "`$0import argparse`n"
}

# 1) Ensure build_args exists (idempotent-ish)
try {
  Patch-RegexOnce -Path $Path -Pattern "(?s)def build_args\(\):" -Replacement "def build_args():"
} catch {
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
}

# 2) Force args usage at start of main (only if not already present)
try {
  Patch-RegexOnce -Path $Path `
    -Pattern "(?s)(def main\([^)]*\):\r?\n)(?!\s*args\s*=\s*build_args\(\))" `
    -Replacement @"
`$1    args = build_args()
    run_id = args.run_id
    runs_dir = args.runs_dir

"@
} catch {
  # If it already has args, skip
}

# 3) Nuke common sys.argv run_id assignments (this is the root bug)
# Covers patterns like:
#   run_id = sys.argv[1]
#   run_id = sys.argv[2]
#   run_id = sys.argv[sys.argv.index("--run-id")+1]
#   RID = sys.argv[1]
$killPatterns = @(
  "(?m)^\s*\w+\s*=\s*sys\.argv\[[^\]]+\]\s*$",
  "(?m)^\s*\w+\s*=\s*sys\.argv\[[^\]]+\]\s*#.*$",
  "(?m)^\s*\w+\s*=\s*sys\.argv\.?\w*\(.*\)\s*$"
)

foreach ($kp in $killPatterns) {
  try {
    Patch-RegexOnce -Path $Path -Pattern $kp -Replacement "    # [HARDENED] removed sys.argv-based parsing; use argparse build_args()"
  } catch {
    # ignore if not found
  }
}

# 4) If sys.argv still used anywhere, fail (we want it dead)
$src = Get-Content -Raw -Encoding UTF8 $Path
if ($src -match "sys\.argv") {
  throw "HARD FAIL: sys.argv still present in run_pipeline.py. Search and remove remaining manual parsing."
}

Write-Host "OK: CLI hardened. sys.argv parsing removed. Use: python run_pipeline.py --run-id <ID>" -ForegroundColor Green
