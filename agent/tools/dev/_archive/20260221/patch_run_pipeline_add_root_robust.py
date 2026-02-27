from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

changed = False

# ---------------- (A) Add --root next to --runs-dir using whatever parser var is used ----------------
if not re.search(r'add_argument\("--root"\b', txt):
    pat_runsdir = r'(?m)^(?P<indent>\s*)(?P<p>\w+)\.add_argument\("--runs-dir".*\)\s*$'
    m = re.search(pat_runsdir, txt)
    if not m:
        raise SystemExit("PATCH FAIL: could not find any <parser>.add_argument(\"--runs-dir\" ...) line.")
    indent = m.group("indent")
    p = m.group("p")
    ins = f'\n{indent}{p}.add_argument("--root", default=None, help="Override scan root (passed to scan stage only)")'
    txt = txt[:m.end()] + ins + txt[m.end():]
    changed = True

# ---------------- (B) Passthrough root ONLY to run_scan_stage.py (inject before subprocess.run) ----------------
if "ROOT_OVERRIDE passthrough (scan stage only)" not in txt:
    # Ensure subprocess is imported somewhere (most likely already is)
    # Inject right before the first subprocess.run(...) call
    pat_run = r'(?m)^(?P<indent>\s*)subprocess\.run\('
    m2 = re.search(pat_run, txt)
    if not m2:
        raise SystemExit("PATCH FAIL: could not find 'subprocess.run(' to inject passthrough before it.")
    indent = m2.group("indent")

    inject = f'''
{indent}# --- ROOT_OVERRIDE passthrough (scan stage only)
{indent}try:
{indent}  if getattr(args, "root", None):
{indent}    rname = str(runner).replace("\\\\","/").split("/")[-1]
{indent}    if rname == "run_scan_stage.py":
{indent}      cmd += ["--root", args.root]
{indent}      step["scan_root_override"] = args.root
{indent}except Exception as _e:
{indent}  step["scan_root_override_error"] = str(_e)

'''
    txt = txt[:m2.start()] + inject + txt[m2.start():]
    changed = True

rp.write_text(txt, encoding="utf-8")
print("PATCH OK" if changed else "PATCH SKIP (already applied)")
