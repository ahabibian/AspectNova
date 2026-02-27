from __future__ import annotations
from pathlib import Path
import re

TARGET = Path("stages") / "builder_scan.py"

def main():
    if not TARGET.exists():
        print(f"NOT FOUND: {TARGET}")
        raise SystemExit(2)

    raw = TARGET.read_text(encoding="utf-8", errors="replace")

    # already fixed?
    if not raw.lstrip().startswith("$CODE"):
        print("REPAIR: builder_scan.py already pure python. OK")
        return

    # strip '$CODE = @"' opener
    raw2 = re.sub(r'^\s*\$CODE\s*=\s*@\"\s*\r?\n', '', raw, count=1)

    # find closer line '"@'
    m = re.search(r'(?m)^\s*\"@\s*$', raw2)
    if not m:
        print('REPAIR FAIL: closer line \'"@\' not found')
        raise SystemExit(3)

    raw2 = raw2[:m.start()].rstrip() + "\n"
    TARGET.write_text(raw2, encoding="utf-8", newline="\n")
    print("REPAIR OK: stripped PowerShell wrapper from stages/builder_scan.py")

if __name__ == "__main__":
    main()