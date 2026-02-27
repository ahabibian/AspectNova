param([string]$RepoRoot = (Get-Location).Path)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $RepoRoot "tools\toolkit.ps1")

$Path = Join-Path $RepoRoot "run_pipeline.py"
if (!(Test-Path $Path)) { throw "run_pipeline.py not found." }

# Replace the sys.argv block with argparse-based args
Patch-RegexOnce -Path $Path `
  -Pattern "(?s)^\s*if\s+len\(sys\.argv\)\s*<\s*2\s*:\s*\r?\n\s*print\(\"usage:\s*python\s+run_pipeline\.py\s*<run_id>\"\)\s*\r?\n\s*raise\s+SystemExit\(2\)\s*\r?\n\s*\r?\n\s*run_id\s*=\s*sys\.argv\[1\]\s*\r?\n" `
  -Replacement @"
  args = build_args()
  run_id = args.run_id
  runs_dir = args.runs_dir

"@

# Ensure evidence path uses runs_dir
Patch-RegexOnce -Path $Path `
  -Pattern "(?m)^\s*E\s*=\s*root\s*/\s*\"runs\"\s*/\s*run_id\s*/\s*\"output\"\s*/\s*\"evidence\"\s*$" `
  -Replacement "  E = root / runs_dir / run_id / ""output"" / ""evidence"""

# Hard fail if sys.argv still exists
$src = Get-Content -Raw -Encoding UTF8 $Path
if ($src -match "sys\.argv") { throw "HARD FAIL: sys.argv still present after patch." }

Write-Host "OK: CLI now uses argparse (--run-id, --runs-dir). sys.argv removed." -ForegroundColor Green
