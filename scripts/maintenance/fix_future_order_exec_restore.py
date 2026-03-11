from pathlib import Path
import re

files = [
    Path(r"tools\execute_cleanup_plan_v1_1.py"),
    Path(r"tools\restore_archive_v1_1.py"),
]

boot_start = "# --- v1.2 bootstrap: allow running tools/*.py directly"
boot_end = "# --- end bootstrap ---"

for p in files:
    src = p.read_text(encoding="utf-8")

    if boot_start not in src or boot_end not in src:
        print("SKIP (no bootstrap markers):", p)
        continue

    before, rest = src.split(boot_start, 1)
    boot_body, after = rest.split(boot_end, 1)
    boot_block = boot_start + boot_body + boot_end + "\n"

    # extract future lines from BEFORE section
    lines = before.splitlines(True)
    future = []
    kept = []
    for line in lines:
        if re.match(r"^\s*from\s+__future__\s+import\s+", line.strip()):
            future.append(line)
        else:
            kept.append(line)

    if not future:
        print("SKIP (no future import):", p)
        continue

    # normalize spacing: ensure one blank line after future block
    new_src = "".join(kept).rstrip() + "\n\n" + "".join(future).strip() + "\n\n" + boot_block + after.lstrip()
    p.write_text(new_src, encoding="utf-8")
    print("OK: moved future above bootstrap:", p)
