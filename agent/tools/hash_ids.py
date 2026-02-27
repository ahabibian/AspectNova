import json, hashlib
from pathlib import Path

p = Path(r"C:\Users\ealihab\OneDrive - Ericsson\Desktop\AspectNova\agent\runs\scan_manual_20260214T083438Z\output\evidence\evidence_pack.v1.json")
d = json.loads(p.read_text(encoding="utf-8"))

ids = sorted([n["id"] for n in d["nodes"]] + [e["id"] for e in d["edges"]])
h = hashlib.sha256(("\n".join(ids)).encode("utf-8")).hexdigest()
print(h)
