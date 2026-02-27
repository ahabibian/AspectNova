from __future__ import annotations
from pathlib import Path

p = Path("run_pipeline.py")
s = p.read_text(encoding="utf-8-sig")

# Fix report names: underscore -> dot
s = s.replace("{E}/manifest_pre.report.json", "{E}/manifest.pre.report.json")
s = s.replace("{E}/manifest_post.report.json", "{E}/manifest.post.report.json")

# Fix gate names if they were also underscored (optional safety)
s = s.replace("{E}/manifest_pre.gate.json", "{E}/manifest.pre.gate.json")
s = s.replace("{E}/manifest_post.gate.json", "{E}/manifest.post.gate.json")

p.write_text(s, encoding="utf-8")
print("PATCH OK: manifest outputs switched to dot-style names")
