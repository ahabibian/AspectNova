from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]

def unwrap_ps_wrapper(text: str) -> str | None:
    # Detect PowerShell wrapper style:
    # $CODE = @"
    # <python...>
    # "@
    lines = text.splitlines()
    if not lines:
        return None
    if not lines[0].lstrip().startswith('$CODE = @"'):
        return None

    # Find end marker line containing '"@'
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '"@':
            end_idx = i
            break
    if end_idx is None:
        return None

    py_lines = lines[1:end_idx]
    # Remove accidental leading "PS C:\...>" prompts if any
    cleaned = []
    for ln in py_lines:
        if ln.lstrip().startswith("PS "):
            continue
        cleaned.append(ln)

    out = "\n".join(cleaned).rstrip() + "\n"
    if "import " not in out and "def " not in out:
        # Heuristic: avoid nuking non-python by mistake
        return None
    return out

def main() -> int:
    fixed = []
    skipped = []
    bad = []
    for p in ROOT.rglob("*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="strict")
        except Exception:
            # fallback
            txt = p.read_text(encoding="utf-8", errors="ignore")

        new = unwrap_ps_wrapper(txt)
        if new is None:
            skipped.append(str(p.relative_to(ROOT)))
            continue

        # write back as UTF-8 no BOM
        p.write_text(new, encoding="utf-8", newline="\n")
        fixed.append(str(p.relative_to(ROOT)))

    print("REPAIR_ALL DONE")
    print("fixed:", fixed)
    print("skipped_count:", len(skipped))
    if not fixed:
        print("NOTE: no wrapper files found.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())