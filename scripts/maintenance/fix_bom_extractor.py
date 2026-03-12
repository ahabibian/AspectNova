from pathlib import Path

p = Path(r"tools\extract_cleanup_targets_v1_1.py")

text = p.read_text(encoding="utf-8-sig")  
p.write_text(text, encoding="utf-8")     

print("OK: BOM removed from", p)
