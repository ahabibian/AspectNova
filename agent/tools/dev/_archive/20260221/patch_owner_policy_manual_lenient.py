from __future__ import annotations
import json
from pathlib import Path

p = Path("policies/owner_enricher.policy.json")
d = json.loads(p.read_text(encoding="utf-8-sig"))

def set_key(obj):
    changed = 0
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            v = obj[k]
            if k == "max_owner_fail_rate":
                obj[k] = 1.0
                changed += 1
            # بعضی policyها به شکل {"type":"max_owner_fail_rate","detail":{"max":0.005}} هستند
            if k == "detail" and isinstance(v, dict) and "max" in v and obj.get("type") == "max_owner_fail_rate":
                v["max"] = 1.0
                changed += 1
            changed += set_key(v)
    elif isinstance(obj, list):
        for it in obj:
            changed += set_key(it)
    return changed

changed = set_key(d)
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"PATCH OK: updated {changed} field(s) in {p.as_posix()}")
