param()

$repo = (git rev-parse --show-toplevel)
if (-not $repo) { throw "Not inside a git repo." }

Set-Location $repo

# Use repo-versioned hooks path
git config core.hooksPath scripts/hooks

Write-Host "OK: configured core.hooksPath = scripts/hooks"

# Quick verify
$hp = git config --get core.hooksPath
Write-Host "hooksPath: $hp"

# Optional: run gate once to prove toolchain is OK
powershell -NoProfile -ExecutionPolicy Bypass -File .\dv.ps1 gate
exit $LASTEXITCODE