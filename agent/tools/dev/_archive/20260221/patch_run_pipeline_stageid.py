from __future__ import annotations

from pathlib import Path

p = Path("run_pipeline.py")
s = p.read_text(encoding="utf-8-sig")

old_loop = "for runner, stage_id, gate, gate_args, must_exist, gate_out in STAGES:"
new_loop = "for runner, gate, gate_args, must_exist, gate_out in STAGES:"

# A) loop must be reverted to 5-tuple exactly once
n = s.count(old_loop)
print("loop6_matches", n)
if n != 1:
    raise SystemExit("ERROR: expected exactly 1 loop(6) line match")
s = s.replace(old_loop, new_loop, 1)

# B) inject stage_id compute block right after the loop line (so it exists before step)
marker = new_loop
pos = s.find(marker)
if pos < 0:
    raise SystemExit("ERROR: loop(5) marker not found after replace")

line_end = s.find("\n", pos)
if line_end < 0:
    raise SystemExit("ERROR: cannot locate end of loop line")

if "canonical stage id for log" not in s:
    inject = (
        "\n"
        "    # --- canonical stage id for log (stable)\n"
        "    stage_id = normalize_stage(Path(runner).stem.replace(\"run_\", \"\").replace(\"_stage\", \"\"))\n"
        "    # manifest split: detect pre/post by gate_out filename\n"
        "    if runner == \"run_manifest_stage.py\":\n"
        "      stage_id = \"manifest_post\" if \"manifest_post\" in str(gate_out) else \"manifest_pre\"\n"
    )
    s = s[: line_end + 1] + inject + s[line_end + 1 :]

# C) ensure step dict includes stage_id (exactly once)
old_step = 'step = {"runner": runner, "gate": gate, "status": "START", "exitcode": None}'
new_step = 'step = {"runner": runner, "stage": stage_id, "gate": gate, "status": "START", "exitcode": None}'

n_old = s.count(old_step)
n_new = s.count(new_step)
print("step_old_matches", n_old, "step_new_matches", n_new)

if n_new == 0:
    if n_old != 1:
        raise SystemExit("ERROR: expected exactly 1 old_step match to patch")
    s = s.replace(old_step, new_step, 1)

p.write_text(s, encoding="utf-8")
print("PATCH OK")
