from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_pipeline.py")
txt = rp.read_text(encoding="utf-8")

# ---------- 0) remove ALL ROOT_OVERRIDE blocks (the broken ones included) ----------
# Remove blocks that start with a ROOT_OVERRIDE marker and include a try/except body.
# We remove from the marker line up to the first blank line AFTER the block.
txt2 = re.sub(
    r'(?ms)^[ \t]*# --- ROOT_OVERRIDE[^\n]*\n.*?(?:\n[ \t]*\n)',
    "\n",
    txt
)

# Also remove any orphan lines that reference scan_root_override_error injected wrongly
txt2 = re.sub(r'(?m)^[ \t]*step\["scan_root_override_error"\].*\n', "", txt2)
txt2 = re.sub(r'(?m)^[ \t]*step\["scan_root_override"\].*\n', "", txt2)

# ---------- 1) dedup argparse --root (keep first, remove rest) ----------
pat_root_arg = r'(?m)^\s*\w+\.add_argument\("--root".*\)\s*$'
ms = list(re.finditer(pat_root_arg, txt2))
if len(ms) > 1:
    out = []
    last = 0
    for i, m in enumerate(ms):
        if i == 0:
            continue
        out.append(txt2[last:m.start()])
        last = m.end()
    out.append(txt2[last:])
    txt2 = "".join(out)

# ---------- 2) inject correct passthrough INSIDE main stage-loop cmd build ----------
marker = "# --- ROOT_OVERRIDE passthrough (scan stage only) [MAIN_LOOP]"
if marker not in txt2:
    m_main = re.search(r'(?m)^def\s+main\s*\(', txt2)
    if not m_main:
        raise SystemExit("REPAIR FAIL: cannot find def main(")

    head = txt2[:m_main.start()]
    tail = txt2[m_main.start():]

    # Find cmd assignment inside main that contains sys.executable AND runner (avoid run_cmd area by working only in tail)
    m_cmd = re.search(
        r'(?m)^(?P<indent>[ \t]*)cmd\s*=\s*\[.*sys\.executable.*\brunner\b.*\]\s*$',
        tail
    )
    if not m_cmd:
        # fallback: cmd list might be multi-line; try a softer pattern
        m_cmd = re.search(
            r'(?m)^(?P<indent>[ \t]*)cmd\s*=\s*\[.*sys\.executable.*$',
            tail
        )
        if not m_cmd:
            raise SystemExit("REPAIR FAIL: cannot find cmd = [...] in main to inject after.")

    indent = m_cmd.group("indent")
    inject = f"""
{indent}{marker}
{indent}try:
{indent}  if getattr(args, "root", None):
{indent}    rname = str(runner).replace("\\\\","/").split("/")[-1]
{indent}    if rname == "run_scan_stage.py" and ("--root" not in cmd):
{indent}      cmd += ["--root", args.root]
{indent}      step["scan_root_override"] = args.root
{indent}except Exception as _e:
{indent}  step["scan_root_override_error"] = str(_e)

"""
    tail = tail[:m_cmd.end()] + inject + tail[m_cmd.end():]
    txt2 = head + tail

rp.write_text(txt2, encoding="utf-8")
print("REPAIRED run_pipeline.py: removed bad ROOT_OVERRIDE blocks + injected correct MAIN_LOOP passthrough + deduped --root")
