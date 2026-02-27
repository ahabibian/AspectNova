from __future__ import annotations
from pathlib import Path
import re

p = Path("run_pipeline.py")
s = p.read_text(encoding="utf-8")

# 1) Ensure main() body starts with an indented line (fix common regex injection damage)
# If immediately after 'def main()' we see a NON-indented 'args = build_args()' (or other), indent it.
s = re.sub(
    r'(def main\(\)\s*->\s*None:\s*\r?\n)(\S)',
    r'\1  \2',
    s,
    count=1
)

# 2) Remove any POST_ARGS_GUARDS block that is NOT indented (safety)
s = re.sub(r'(?m)^(POST_ARGS_GUARDS.*)$', r'  \1', s)

# 3) Remove any incorrectly placed unindented args assignment (outside main)
# If there's a line '^args = build_args()' that is not indented, indent it.
s = re.sub(r'(?m)^args\s*=\s*build_args\(\)\s*$', r'  args = build_args()', s, count=1)

# 4) Now ensure we have the correct guard block AFTER the (indented) args line
guard_marker = "POST_ARGS_GUARDS"
if guard_marker not in s:
    block = """
  # --- POST_ARGS_GUARDS (devguard + selftest)
  rc, out, err = run_cmd([sys.executable, "tools/dev/devguard.py"])
  if rc != 0 or "OK" not in (out + err):
    print(json.dumps({"status":"FAIL","where":"devguard","stdout":out,"stderr":err}, indent=2))
    raise SystemExit(9)

  rc, out, err = run_cmd([sys.executable, "tools/dev/selftest.py"])
  if rc != 0 or '"status": "OK"' not in (out + err):
    print(json.dumps({"status":"FAIL","where":"selftest","stdout":out,"stderr":err}, indent=2))
    raise SystemExit(11)

  if getattr(args, "selftest_only", False):
    print(json.dumps({"status":"OK","where":"selftest_only"}, indent=2))
    raise SystemExit(0)
"""
    # Insert right after the FIRST indented args assignment inside main
    s2, n = re.subn(r'(?m)^\s{2}args\s*=\s*build_args\(\)\s*$', lambda m: m.group(0) + block, s, count=1)
    s = s2

p.write_text(s, encoding="utf-8")
print("REPAIR_MAIN_INDENT OK")