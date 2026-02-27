from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

changed = False

# ---------- (A) Add argparse --root ----------
if not re.search(r'add_argument\("--root"\b', txt):
    # Insert right after the --runs-dir argument if possible
    pat = r'(?m)^(?P<indent>\s*)ap\.add_argument\("--runs-dir".*\)\s*$'
    m = re.search(pat, txt)
    if m:
        indent = m.group("indent")
        ins = f'\n{indent}ap.add_argument("--root", default=None, help="Override scan root (passed to scan stage only)")'
        txt = txt[:m.end()] + ins + txt[m.end():]
        changed = True
    else:
        # fallback: insert after ap = argparse.ArgumentParser(...)
        pat2 = r'(?m)^(?P<indent>\s*)ap\s*=\s*argparse\.ArgumentParser\([^)]*\)\s*$'
        m2 = re.search(pat2, txt)
        if not m2:
            raise SystemExit("PATCH FAIL: could not find argparse parser creation to insert --root.")
        indent = m2.group("indent")
        ins = f'\n{indent}ap.add_argument("--root", default=None, help="Override scan root (passed to scan stage only)")'
        txt = txt[:m2.end()] + ins + txt[m2.end():]
        changed = True

# ---------- (B) Passthrough root ONLY to run_scan_stage.py ----------
# We inject after the first 'cmd = [...]' line.
if "ROOT_OVERRIDE passthrough (scan stage only)" not in txt:
    pat_cmd = r'(?m)^(?P<indent>\s*)cmd\s*=\s*\[.*\]\s*$'
    m = re.search(pat_cmd, txt)
    if not m:
        raise SystemExit("PATCH FAIL: could not find a 'cmd = [...]' line to inject passthrough.")
    indent = m.group("indent")

    inject = f'''
{indent}# --- ROOT_OVERRIDE passthrough (scan stage only)
{indent}try:
{indent}  if getattr(args, "root", None):
{indent}    # runner may be 'run_scan_stage.py' or a path; normalize by basename
{indent}    rname = str(runner).replace("\\\\","/").split("/")[-1]
{indent}    if rname == "run_scan_stage.py":
{indent}      cmd += ["--root", args.root]
{indent}      step["scan_root_override"] = args.root
{indent}except Exception as _e:
{indent}  step["scan_root_override_error"] = str(_e)
'''
    txt = txt[:m.end()] + "\n" + inject + txt[m.end():]
    changed = True

rp.write_text(txt, encoding="utf-8")
print("PATCH OK" if changed else "PATCH SKIP (already applied)")
