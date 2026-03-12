from pathlib import Path
import re

FILES = [
    Path(r"tools\extract_cleanup_targets_v1_1.py"),
    Path(r"tools\execute_cleanup_plan_v1_1.py"),
    Path(r"tools\restore_archive_v1_1.py"),
]

BOOT = """
# --- v1.2 bootstrap: allow running tools/*.py directly (tests call: python tools\\x.py)
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
# --- end bootstrap ---
"""

def backup(p: Path):
    b = p.with_suffix(p.suffix + ".v1_2_step2_pathfix.bak")
    b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    return b

def already_has_boot(src: str) -> bool:
    return "v1.2 bootstrap: allow running tools/*.py directly" in src or "sys.path.insert(0" in src

def inject_bootstrap(src: str) -> str:
    if already_has_boot(src):
        return src

    lines = src.splitlines(True)

    # place after shebang/encoding and module docstring if present, else near top
    i = 0
    if lines and lines[0].startswith("#!"):
        i = 1
    if i < len(lines) and re.match(r"^#.*coding[:=]\s*utf-8", lines[i]):
        i += 1

    # skip blank lines
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    # skip module docstring block if present
    if i < len(lines) and lines[i].lstrip().startswith(('"""', "'''")):
        q = lines[i].lstrip()[:3]
        i += 1
        while i < len(lines) and q not in lines[i]:
            i += 1
        if i < len(lines):
            i += 1  # include closing line
        while i < len(lines) and lines[i].strip() == "":
            i += 1

    # inject bootstrap here
    lines.insert(i, BOOT + "\n")
    return "".join(lines)

def main():
    for p in FILES:
        if not p.exists():
            raise SystemExit(f"ERROR: missing {p}")
        bak = backup(p)
        src = p.read_text(encoding="utf-8")
        patched = inject_bootstrap(src)
        p.write_text(patched, encoding="utf-8")
        print(f"OK: injected bootstrap into {p} (backup: {bak.name})")

if __name__ == "__main__":
    main()
