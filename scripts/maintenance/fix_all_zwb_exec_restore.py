from pathlib import Path

files = [
    Path(r"tools\execute_cleanup_plan_v1_1.py"),
    Path(r"tools\restore_archive_v1_1.py"),
]

for p in files:
    raw = p.read_text(encoding="utf-8", errors="replace")
    clean = raw.replace("\ufeff", "")
    p.write_text(clean, encoding="utf-8")
    print("OK: removed U+FEFF from", p, "| removed=", (len(raw) - len(clean)))
