from pathlib import Path

p = Path(r"tools\extract_cleanup_targets_v1_1.py")

raw = p.read_text(encoding="utf-8", errors="replace")
clean = raw.replace("\ufeff", "")

p.write_text(clean, encoding="utf-8")

print("OK: removed all U+FEFF from", p, "| removed=", (len(raw) - len(clean)))
