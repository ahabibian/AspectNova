from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

changed = False

# A) Ensure argparse --root exists (insert next to --runs-dir)
if not re.search(r'add_argument\("--root"\b', txt):
    m = re.search(r'(?m)^(?P<indent>\s*)(?P<p>\w+)\.add_argument\("--runs-dir".*\)\s*$', txt)
    if not m:
        raise SystemExit("PATCH FAIL: cannot find --runs-dir add_argument line.")
    indent, p = m.group("indent"), m.group("p")
    txt = txt[:m.end()] + f'\n{indent}{p}.add_argument("--root", default=None, help="Override scan root (scan stage only)")' + txt[m.end():]
    changed = True

# B) Inject right before subprocess.run(cmd...) INSIDE the stage execution
if "ROOT_OVERRIDE passthrough (scan stage only) [IN_LOOP]" not in txt:
    m2 = re.search(r'(?m)^(?P<indent>\s*)subprocess\.run\(\s*cmd\b', txt)
    if not m2:
        raise SystemExit("PATCH FAIL: cannot find 'subprocess.run(cmd' to inject before.")
    indent = m2.group("indent")

    inject = f"""{indent}# --- ROOT_OVERRIDE passthrough (scan stage only) [IN_LOOP]
{indent}try:
{indent}  if getattr(args, "root", None):
{indent}    rname = str(runner).replace("\\\\","/").split("/")[-1]
{indent}    if rname == "run_scan_stage.py" and ("--root" not in cmd):
{indent}      cmd += ["--root", args.root]
{indent}      step["scan_root_override"] = args.root
{indent}except Exception as _e:
{indent}  step["scan_root_override_error"] = str(_e)

"""
    txt = txt[:m2.start()] + inject + txt[m2.start():]
    changed = True

rp.write_text(txt, encoding="utf-8")
print("PATCH OK" if changed else "PATCH SKIP")
