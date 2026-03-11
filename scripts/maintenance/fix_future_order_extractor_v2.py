from pathlib import Path

p = Path(r"tools\extract_cleanup_targets_v1_1.py")
src = p.read_text(encoding="utf-8")

boot_marker = "v1.2 bootstrap: allow running tools/*.py directly"

# جدا کردن bootstrap
parts = src.split("# --- v1.2 bootstrap: allow running tools/*.py directly")
if len(parts) < 2:
    raise SystemExit("Bootstrap block not found")

before_boot = parts[0]
boot_block = "# --- v1.2 bootstrap: allow running tools/*.py directly" + parts[1].split("# --- end bootstrap ---")[0] + "# --- end bootstrap ---\n"
after_boot = parts[1].split("# --- end bootstrap ---")[1]

# پیدا کردن future import
lines = before_boot.splitlines(True)
new_before = []
future_lines = []

for line in lines:
    if line.strip().startswith("from __future__ import"):
        future_lines.append(line)
    else:
        new_before.append(line)

if not future_lines:
    raise SystemExit("No future import found")

# بازسازی فایل
new_src = "".join(new_before) + "".join(future_lines) + "\n" + boot_block + after_boot

p.write_text(new_src, encoding="utf-8")
print("OK: future-import moved above bootstrap")
