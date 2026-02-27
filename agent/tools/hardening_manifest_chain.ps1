param(
  [string]$RepoRoot = (Get-Location).Path,
  [string]$OutDirRel = "out"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load toolkit (Write-TextUtf8NoBom, Patch-RegexOnce)
. (Join-Path $RepoRoot "tools\toolkit.ps1")

$OutDir = Join-Path $RepoRoot $OutDirRel
$LibDir = Join-Path $RepoRoot "agent\src\lib"
$ManifestLib = Join-Path $LibDir "manifest_chain.py"

# --- 1) Create manifest_chain.py (new lib) ---
$manifestLibContent = @'
import json
import os
import hashlib
from datetime import datetime, timezone

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def ledger_path(out_dir: str) -> str:
    return os.path.join(out_dir, "_ledger", "latest_manifest_sha256.txt")

def read_previous_manifest_sha(out_dir: str) -> str | None:
    lp = ledger_path(out_dir)
    if not os.path.exists(lp):
        return None
    with open(lp, "r", encoding="utf-8") as f:
        s = f.read().strip()
        return s or None

def write_latest_manifest_sha(out_dir: str, manifest_sha: str) -> None:
    lp = ledger_path(out_dir)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    with open(lp, "w", encoding="utf-8", newline="\n") as f:
        f.write(manifest_sha + "\n")

def attach_chain_fields(manifest: dict, out_dir: str) -> dict:
    prev = read_previous_manifest_sha(out_dir)
    if prev:
        manifest["previous_manifest_sha256"] = prev
    manifest.setdefault("created_utc", utc_now_iso())
    return manifest

def finalize_manifest_chain(out_dir: str, manifest_path: str) -> str:
    # Compute and persist manifest hash as the new ledger head
    msha = sha256_file(manifest_path)
    write_latest_manifest_sha(out_dir, msha)
    return msha
'@

# Ensure directory exists
if (!(Test-Path $LibDir)) { New-Item -ItemType Directory -Path $LibDir -Force | Out-Null }
Write-TextUtf8NoBom -Path $ManifestLib -Text $manifestLibContent

# --- 2) Patch run_pipeline.py to enable deterministic defaults ---
$RunPipeline = Join-Path $RepoRoot "run_pipeline.py"
if (!(Test-Path $RunPipeline)) { throw "run_pipeline.py not found at repo root." }

# Add deterministic env defaults near imports (best-effort)
Patch-RegexOnce -Path $RunPipeline `
  -Pattern "(?s)^(import .+?\n)(\n)" `
  -Replacement "`$1import os`nimport random`n`n`$2"

# Seed + force UTC/locale-ish stability at program start (best-effort injection)
Patch-RegexOnce -Path $RunPipeline `
  -Pattern "(?s)(def main\([^)]*\):\n)" `
  -Replacement "`$1    # Deterministic defaults (production hardening)`n    seed = int(os.environ.get('ASPECTNOVA_SEED','42'))`n    random.seed(seed)`n    os.environ.setdefault('TZ','UTC')`n"

# --- 3) Patch manifest creation to attach chain fields (best-effort) ---
# We look for a dict named manifest or a write to manifest.json; inject chain attach before write.
Patch-RegexOnce -Path $RunPipeline `
  -Pattern "(?s)(manifest\s*=\s*\{.*?\}\n)" `
  -Replacement "`$1`n    # Attach ledger chain fields`n    try:`n        from agent.src.lib.manifest_chain import attach_chain_fields`n        manifest = attach_chain_fields(manifest, out_dir)`n    except Exception:`n        pass`n"

# --- 4) After manifest is written, finalize ledger head ---
# Inject finalize call near integrity stage or immediately after manifest write.
Patch-RegexOnce -Path $RunPipeline `
  -Pattern "(?s)(manifest_path\s*=\s*.*?manifest\.json.*?\n)" `
  -Replacement "`$1    # Finalize manifest chain ledger head`n    try:`n        from agent.src.lib.manifest_chain import finalize_manifest_chain`n        _msha = finalize_manifest_chain(out_dir, manifest_path)`n    except Exception:`n        pass`n"

# --- 5) Create a small readme for ops ---
$OpsNote = Join-Path $RepoRoot "docs\HARDENING_MANIFEST_CHAIN.md"
if (!(Test-Path (Split-Path $OpsNote))) { New-Item -ItemType Directory -Path (Split-Path $OpsNote) -Force | Out-Null }

$opsContent = @"
# Manifest Chain + Determinism (Hardening)

- Each run's manifest may include `previous_manifest_sha256` pointing to the previous run manifest hash.
- The current ledger head is stored at: `$OutDirRel\_ledger\latest_manifest_sha256.txt`
- Determinism defaults:
  - env ASPECTNOVA_SEED (default 42)
  - TZ forced to UTC if not set

To reset ledger head (ONLY if you intentionally start a new audit chain):
- delete `$OutDirRel\_ledger\latest_manifest_sha256.txt`
"@
Write-TextUtf8NoBom -Path $OpsNote -Text $opsContent

Write-Host "OK: manifest chain lib + run_pipeline patches applied." -ForegroundColor Green
Write-Host "Next: run lint_repo.ps1 and a pipeline run to confirm PASS." -ForegroundColor Yellow
