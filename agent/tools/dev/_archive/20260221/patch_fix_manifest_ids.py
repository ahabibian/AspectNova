from __future__ import annotations

from pathlib import Path

p = Path("run_pipeline.py")
s = p.read_text(encoding="utf-8-sig")

old_pre = '("run_manifest_stage.py",     "manifest_pre", "tools/gate_manifest.py",\n    ["{E}/manifest.report.json", "policies/manifest.policy.json"],\n    "{E}/manifest.report.json", "{E}/manifest.gate.json"),'
new_pre = '("run_manifest_stage.py",     "manifest_pre", "tools/gate_manifest.py",\n    ["{E}/manifest_pre.report.json", "policies/manifest.policy.json"],\n    "{E}/manifest_pre.report.json", "{E}/manifest_pre.gate.json"),'

old_post = '("run_manifest_stage.py",     "manifest_pre", "tools/gate_manifest.py",\n    ["{E}/manifest.report.json", "policies/manifest.policy.json"],\n    "{E}/manifest.report.json", "{E}/manifest_post.gate.json"),'
new_post = '("run_manifest_stage.py",     "manifest_post", "tools/gate_manifest.py",\n    ["{E}/manifest_post.report.json", "policies/manifest.policy.json"],\n    "{E}/manifest_post.report.json", "{E}/manifest_post.gate.json"),'

c1 = s.count(old_pre)
c2 = s.count(old_post)

print("pre_match", c1, "post_match", c2)

if c1 != 1:
    raise SystemExit("ERROR: expected exactly 1 pre manifest tuple match")
if c2 != 1:
    raise SystemExit("ERROR: expected exactly 1 post manifest tuple match")

s = s.replace(old_pre, new_pre, 1)
s = s.replace(old_post, new_post, 1)

p.write_text(s, encoding="utf-8")
print("PATCH OK: manifest_pre/manifest_post ids + unique outputs")
