from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

# --- 1) define I next to O/E
pat_vars = r'(O\s*=\s*root\s*/\s*runs_dir\s*/\s*run_id\s*/\s*"output"\s*\r?\n\s*E\s*=\s*O\s*/\s*"evidence")'
if re.search(pat_vars, txt) and not re.search(r"^\s*I\s*=", txt, re.M):
    txt = re.sub(pat_vars, r'\1\n\n  I = root / runs_dir / run_id / "input"', txt, count=1)

# --- 2) insert scan stage after preflight
if "run_scan_stage.py" not in txt:
    insert = '''
  # --- scan stage (creates runs/<run_id>/input/scan_result.json)
  ("run_scan_stage.py",         "tools/gate_scan_stage.py",
    ["{I}/scan_result.json"],
    "{I}/scan_result.json", "{E}/scan_stage.gate.json"),

'''
    pat_preflight = r'(\("run_preflight_stage\.py".*?\),\s*\r?\n)'
    m = re.search(pat_preflight, txt, flags=re.S)
    if not m:
        raise SystemExit("Could not find preflight stage block to insert after.")
    txt = txt[:m.end()] + insert + txt[m.end():]

# --- 3) expand {I} in must_exist path building
txt = re.sub(
    r'replace\(\s*"\{O\}"\s*,\s*str\(O\)\.replace\("\\\\",\s*"/"\)\s*\)\.replace\(\s*"\{E\}"\s*,\s*str\(E\)\.replace\("\\\\",\s*"/"\)\s*\)',
    r'replace("{I}", str(I).replace("\\\\","/")).replace("{O}", str(O).replace("\\\\","/")).replace("{E}", str(E).replace("\\\\","/"))',
    txt,
    count=1
)

# --- 4) expand {I} in gate args building
txt = re.sub(
    r'a2\s*=\s*a2\.replace\(\s*"\{O\}"\s*,\s*str\(O\)\.replace\("\\\\",\s*"/"\)\s*\)\.replace\(\s*"\{E\}"\s*,\s*str\(E\)\.replace\("\\\\",\s*"/"\)\s*\)',
    r'a2 = a2.replace("{I}", str(I).replace("\\\\","/")).replace("{O}", str(O).replace("\\\\","/")).replace("{E}", str(E).replace("\\\\","/"))',
    txt,
    count=1
)

rp.write_text(txt, encoding="utf-8")
print("PATCHED run_pipeline.py OK")
