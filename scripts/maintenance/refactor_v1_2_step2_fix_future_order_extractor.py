from pathlib import Path
import re

P = Path(r"tools\extract_cleanup_targets_v1_1.py")

def backup():
    b = P.with_suffix(P.suffix + ".v1_2_step2_futurefix.bak")
    b.write_text(P.read_text(encoding="utf-8"), encoding="utf-8")
    return b

def main():
    if not P.exists():
        raise SystemExit("missing " + str(P))

    backup()

    src = P.read_text(encoding="utf-8")
    lines = src.splitlines(True)

    # detect module docstring range (optional)
    i = 0
    shebang = False
    if lines and lines[0].startswith("#!"):
        shebang = True
        i = 1

    # encoding line (optional)
    if i < len(lines) and re.match(r"^#.*coding[:=]\s*utf-8", lines[i]):
        i += 1

    # skip blank lines
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    doc_start = None
    doc_end = None
    if i < len(lines) and lines[i].lstrip().startswith(('"""', "'''")):
        q = lines[i].lstrip()[:3]
        doc_start = i
        i += 1
        while i < len(lines):
            if q in lines[i]:
                doc_end = i
                i += 1
                break
            i += 1

    # find any future import line index
    future_idx = None
    for idx, line in enumerate(lines[:80]):
        if re.match(r"^\s*from\s+__future__\s+import\s+annotations\s*$", line.strip()):
            future_idx = idx
            break

    # remove existing bootstrap block (if any)
    def is_boot_line(s: str) -> bool:
        return ("v1.2 bootstrap: allow running tools/*.py directly" in s
                or "sys.path.insert(0" in s
                or "from pathlib import Path as _Path" in s)

    new_lines = []
    for line in lines:
        if is_boot_line(line):
            continue
        new_lines.append(line)
    lines = new_lines

    # also remove duplicate blank lines introduced by removal
    # (light normalize)
    normalized = []
    prev_blank = False
    for line in lines:
        blank = (line.strip() == "")
        if blank and prev_blank:
            continue
        normalized.append(line)
        prev_blank = blank
    lines = normalized

    # remove future import if exists (we will reinsert)
    if future_idx is not None:
        tmp = []
        for line in lines:
            if re.match(r"^\s*from\s+__future__\s+import\s+annotations\s*$", line.strip()):
                continue
            tmp.append(line)
        lines = tmp

    # rebuild header: shebang/encoding/docstring remain where they are.
    # insert future import right after docstring (or after encoding if no docstring)
    insert_pos = 0
    # find position after shebang+encoding+docstring
    insert_pos = 0
    if lines and lines[0].startswith("#!"):
        insert_pos = 1
    if insert_pos < len(lines) and re.match(r"^#.*coding[:=]\s*utf-8", lines[insert_pos]):
        insert_pos += 1

    # skip blanks
    while insert_pos < len(lines) and lines[insert_pos].strip() == "":
        insert_pos += 1

    # if docstring starts here, skip it
    if insert_pos < len(lines) and lines[insert_pos].lstrip().startswith(('"""', "'''")):
        q = lines[insert_pos].lstrip()[:3]
        insert_pos += 1
        while insert_pos < len(lines):
            if q in lines[insert_pos]:
                insert_pos += 1
                break
            insert_pos += 1

    # after docstring, skip blanks
    while insert_pos < len(lines) and lines[insert_pos].strip() == "":
        insert_pos += 1

    FUTURE = "from __future__ import annotations\n"
    BOOT = (
        "# --- v1.2 bootstrap: allow running tools/*.py directly (tests call: python tools\\\\x.py)\n"
        "import sys\n"
        "from pathlib import Path as _Path\n"
        "sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))\n"
        "# --- end bootstrap ---\n\n"
    )

    # insert future only if file previously had it (conservative) OR if typing uses | operator
    # We'll detect 'str | Path' pattern usage; if present, keep future.
    needs_future = ("str | Path" in "".join(lines)) or ("from __future__ import annotations" in src)
    to_insert = ""
    if needs_future:
        to_insert += FUTURE + "\n"
    to_insert += BOOT

    lines.insert(insert_pos, to_insert)

    P.write_text("".join(lines), encoding="utf-8")
    print("OK: fixed future-import order + bootstrap placement in", P)

if __name__ == "__main__":
    main()
