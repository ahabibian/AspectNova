from __future__ import annotations
from pathlib import Path
import re

p = Path("run_pipeline.py")
txt = p.read_text(encoding="utf-8")

# Find all --root add_argument lines (single-line)
pat = r'(?m)^\s*\w+\.add_argument\("--root".*\)\s*$'
matches = list(re.finditer(pat, txt))

if len(matches) <= 1:
    print(f"OK: root arg count = {len(matches)} (no cleanup needed)")
    raise SystemExit(0)

# Keep the first occurrence, remove the rest
keep = matches[0].span()
out = []
last = 0
removed = 0

for i, m in enumerate(matches):
    if i == 0:
        continue
    out.append(txt[last:m.start()])
    last = m.end()
    removed += 1

out.append(txt[last:])
new_txt = "".join(out)

p.write_text(new_txt, encoding="utf-8")
print(f"CLEANED: removed {removed} duplicate --root add_argument lines (kept first)")
