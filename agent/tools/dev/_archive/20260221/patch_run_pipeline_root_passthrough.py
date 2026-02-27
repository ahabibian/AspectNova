from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

# 1) add argparse option --root if missing
if "--root" not in txt:
    # try to insert after --runs-dir
    txt = re.sub(
        r'(?m)^(.*ap\.add_argument\("--runs-dir".*)$',
        r'\1\n  ap.add_argument("--root", default=None, help="Override scan root (passed to scan stage only)")',
        txt,
        count=1
    )

# 2) inject scan-stage arg append (before subprocess/run execution)
# We look for a place where cmd args list exists. We'll inject just after cmd is built.
marker_pat = r'(?m)^\s*cmd\s*=\s*\[.*?\]\s*$'
m = re.search(marker_pat, txt)
if not m:
    # fallback: find "cmd = [sys.executable" or similar
    marker_pat = r'(?m)^\s*cmd\s*=\s*\[sys\.executable.*?\]\s*$'
    m = re.search(marker_pat, txt)

if not m:
    raise SystemExit("Could not find cmd = [...] line in run_pipeline.py to inject root passthrough.")

inject = r'''
    # --- ROOT_OVERRIDE passthrough (scan stage only)
    try:
      if getattr(args, "root", None) and (runner.replace("\\\\","/").endswith("run_scan_stage.py")):
        cmd += ["--root", args.root]
        step["scan_root_override"] = args.root
    except Exception as _e:
      step["scan_root_override_error"] = str(_e)
'''

# Insert right after first cmd = [...] line
txt = txt[:m.end()] + "\n" + inject + txt[m.end():]

rp.write_text(txt, encoding="utf-8")
print("PATCHED run_pipeline.py OK (--root passthrough)")
