from pathlib import Path
import re
from datetime import datetime

FILES = [
    Path(r"tools\extract_cleanup_targets_v1_1.py"),
    Path(r"tools\execute_cleanup_plan_v1_1.py"),
    Path(r"tools\restore_archive_v1_1.py"),
]

IMPORT_BLOCK = """
from core.storage.io_json import read_json, write_json
from core.storage.hash_utils import sha256_file
"""

def backup(p: Path):
    stamp = "v1_2_step2"
    b = p.with_suffix(p.suffix + f".{stamp}.bak")
    b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    return b

def ensure_imports(src: str) -> str:
    if "from core.storage.io_json import read_json, write_json" in src:
        return src

    # insert after last standard import line block
    lines = src.splitlines(True)
    # find insertion point: after the last import or from-import at top
    ins = 0
    for i, line in enumerate(lines[:200]):
        if re.match(r"^\s*(import\s+|from\s+\S+\s+import\s+)", line):
            ins = i + 1
    lines.insert(ins, IMPORT_BLOCK + "\n")
    return "".join(lines)

def rename_legacy_funcs(src: str) -> str:
    # rename any local definitions so the imported ones are used
    patterns = {
        r"^(\s*)def\s+read_json\s*\(": r"\1def _legacy_read_json(",
        r"^(\s*)def\s+write_json\s*\(": r"\1def _legacy_write_json(",
        r"^(\s*)def\s+sha256_file\s*\(": r"\1def _legacy_sha256_file(",
        r"^(\s*)def\s+sha256_bytes\s*\(": r"\1def _legacy_sha256_bytes(",
    }
    out_lines = []
    for line in src.splitlines(True):
        for pat, rep in patterns.items():
            if re.match(pat, line):
                line = re.sub(pat, rep, line)
                break
        out_lines.append(line)
    return "".join(out_lines)

def main():
    for p in FILES:
        if not p.exists():
            raise SystemExit(f"ERROR: missing {p}")
        bak = backup(p)
        src = p.read_text(encoding="utf-8")

        src2 = ensure_imports(src)
        src3 = rename_legacy_funcs(src2)

        p.write_text(src3, encoding="utf-8")
        print(f"OK: patched {p} (backup: {bak.name})")

    print("DONE. Next: run tests/e2e/run_all.ps1")

if __name__ == "__main__":
    main()
