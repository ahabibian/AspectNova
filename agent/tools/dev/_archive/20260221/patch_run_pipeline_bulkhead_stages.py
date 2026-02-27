from __future__ import annotations

from pathlib import Path
import re

p = Path("run_pipeline.py")
lines = p.read_text(encoding="utf-8-sig").splitlines(True)  # keep newlines

# 1) Find the STAGES loop line (5-tuple form)
loop_re = re.compile(r'^(\s*)for\s+runner\s*,\s*gate\s*,\s*gate_args\s*,\s*must_exist\s*,\s*gate_out\s+in\s+STAGES\s*:\s*$')
loop_idx = None
indent = ""

for i, ln in enumerate(lines):
    if loop_re.match(ln.rstrip("\n")):
        loop_idx = i
        indent = loop_re.match(ln.rstrip("\n")).group(1)
        break

if loop_idx is None:
    raise SystemExit("ERROR: STAGES loop line not found in expected 5-tuple form.")

# 2) Replace loop header with single-iterator loop
lines[loop_idx] = f"{indent}for _stage in STAGES:\n"

# 3) Remove any previously injected canonical stage block (avoid duplicates)
marker_re = re.compile(r'^\s*#\s*---\s*canonical stage id for log')
start = None
end = None
for i, ln in enumerate(lines):
    if marker_re.search(ln):
        start = i
        for j in range(i, min(i + 60, len(lines))):
            if lines[j].strip() == "":
                end = j + 1
                break
        if end is None:
            end = start + 1
        break

if start is not None:
    del lines[start:end]

# 4) Insert robust unpack block right after loop header
block = [
    f"{indent}  if len(_stage) == 5:\n",
    f"{indent}    runner, gate, gate_args, must_exist, gate_out = _stage\n",
    f"{indent}    # --- canonical stage id for log (stable)\n",
    f"{indent}    stage_id = normalize_stage(Path(runner).stem.replace(\"run_\", \"\").replace(\"_stage\", \"\"))\n",
    f"{indent}    # manifest split: detect pre/post by gate_out filename\n",
    f"{indent}    if runner == \"run_manifest_stage.py\":\n",
    f"{indent}      stage_id = \"manifest_post\" if \"manifest_post\" in str(gate_out) else \"manifest_pre\"\n",
    f"{indent}  elif len(_stage) == 6:\n",
    f"{indent}    runner, stage_id, gate, gate_args, must_exist, gate_out = _stage\n",
    f"{indent}  else:\n",
    f"{indent}    raise ValueError(\"Invalid STAGES entry length=%s entry=%r\" % (len(_stage), _stage))\n",
    f"{indent}\n",
]

insert_at = loop_idx + 1
lines[insert_at:insert_at] = block

p.write_text("".join(lines), encoding="utf-8")
print("PATCH OK: bulkhead STAGES (accepts 5 or 6)")
