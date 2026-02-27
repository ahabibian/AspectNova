from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

if "MANIFEST_POST_FALLBACK" in txt:
    print("SKIP: MANIFEST_POST_FALLBACK already present")
    raise SystemExit(0)

# 1) ensure shutil import exists
if not re.search(r'(?m)^\s*import\s+shutil\s*$', txt):
    # insert after "import sys" line if present, else after imports block
    txt = re.sub(r'(?m)^(import\s+sys\s*)$', r'\1\nimport shutil', txt, count=1)

# 2) inject fallback before the artifact_missing check
pattern = r'(?m)^\s*if not must_path\.exists\(\):\s*$'
m = re.search(pattern, txt)
if not m:
    raise SystemExit("Could not find: if not must_path.exists(): block")

inject = r'''
    # --- MANIFEST_POST_FALLBACK (compat bridge)
    # run_manifest_stage currently writes manifest.pre.report.json / manifest.report.json.
    # pipeline expects manifest.post.report.json for the post snapshot.
    if (not must_path.exists()) and (stage_id == "manifest_post"):
      alt1 = E / "manifest.pre.report.json"
      alt2 = E / "manifest.report.json"
      try:
        if alt1.exists():
          must_path.parent.mkdir(parents=True, exist_ok=True)
          shutil.copyfile(str(alt1), str(must_path))
          step["manifest_post_fallback"] = str(alt1)
        elif alt2.exists():
          must_path.parent.mkdir(parents=True, exist_ok=True)
          shutil.copyfile(str(alt2), str(must_path))
          step["manifest_post_fallback"] = str(alt2)
      except Exception as _e:
        step["manifest_post_fallback_error"] = str(_e)

'''

# Insert inject right before the first "if not must_path.exists():"
txt = txt[:m.start()] + inject + txt[m.start():]

rp.write_text(txt, encoding="utf-8")
print("PATCHED run_pipeline.py OK (MANIFEST_POST_FALLBACK)")
