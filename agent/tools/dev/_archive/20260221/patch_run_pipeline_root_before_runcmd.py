from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

marker = "# --- ROOT_OVERRIDE passthrough (scan stage only) [BEFORE_RUN_CMD]"
if marker in txt:
    print("PATCH SKIP: already present")
    raise SystemExit(0)

# Find the line where stage execution happens: rc, out, err = run_cmd(cmd)
m = re.search(r'(?m)^(?P<indent>\s*)rc\s*,\s*out\s*,\s*err\s*=\s*run_cmd\(\s*cmd\s*\)\s*$', txt)
if not m:
    raise SystemExit("PATCH FAIL: cannot find 'rc, out, err = run_cmd(cmd)' line.")

indent = m.group("indent")

inject = f"""{indent}{marker}
{indent}try:
{indent}  if getattr(args, "root", None):
{indent}    st = str(step.get("stage",""))
{indent}    if st == "scan" and ("--root" not in cmd):
{indent}      cmd += ["--root", args.root]
{indent}      step["scan_root_override"] = args.root
{indent}  step["cmd_preview"] = cmd[:10]
{indent}except Exception as _e:
{indent}  step["scan_root_override_error"] = str(_e)

"""

txt2 = txt[:m.start()] + inject + txt[m.start():]
rp.write_text(txt2, encoding="utf-8")
print("PATCHED: injected ROOT override before run_cmd(cmd) for scan stage")
