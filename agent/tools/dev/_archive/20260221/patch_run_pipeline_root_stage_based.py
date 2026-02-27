from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

# 1) locate MAIN_LOOP block we injected
# We will replace its body with a stage-based check (scan stage) + cmd logging.
pat = r'(?ms)^[ \t]*# --- ROOT_OVERRIDE passthrough \(scan stage only\) \[MAIN_LOOP\].*?\n[ \t]*\n'
m = re.search(pat, txt)
if not m:
    raise SystemExit("PATCH FAIL: could not find [MAIN_LOOP] ROOT_OVERRIDE block to replace.")

replacement = r'''
      # --- ROOT_OVERRIDE passthrough (scan stage only) [MAIN_LOOP]
      # Robust rule: use stage/stage_id, not runner basename.
      try:
        if getattr(args, "root", None):
          st = str(step.get("stage",""))
          sid = str(step.get("stage_id",""))
          if (st == "scan") or (sid == "scan") or ("scan" in st.lower()) or ("scan" in sid.lower()):
            if "--root" not in cmd:
              cmd += ["--root", args.root]
            step["scan_root_override"] = args.root
          # always record cmd for debugging (first 10 args)
          step["cmd_preview"] = cmd[:10]
      except Exception as _e:
        step["scan_root_override_error"] = str(_e)

'''

txt2 = txt[:m.start()] + replacement + txt[m.end():]
rp.write_text(txt2, encoding="utf-8")
print("PATCHED: ROOT_OVERRIDE MAIN_LOOP now stage-based + cmd_preview")
