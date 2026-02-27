from __future__ import annotations

from pathlib import Path

p = Path("run_pipeline.py")
lines = p.read_text(encoding="utf-8-sig").splitlines(True)

# Find the line: if not runner_path.exists():
target = "if not runner_path.exists():"
idx = None
for i, ln in enumerate(lines):
    if target in ln:
        idx = i
        break

if idx is None:
    raise SystemExit("ERROR: could not find 'if not runner_path.exists():' in run_pipeline.py")

indent = lines[idx].split("if not")[0]  # keep existing indentation

# Check if runner_path already exists in the few lines above
window = "".join(lines[max(0, idx-8):idx])
if "runner_path = " in window and "gate_path = " in window:
    print("SKIP: runner_path/gate_path already appear above the check.")
else:
    inject = [
        f"{indent}runner_path = root / runner\n",
        f"{indent}gate_path = root / gate\n",
    ]
    lines[idx:idx] = inject
    p.write_text("".join(lines), encoding="utf-8")
    print("PATCH OK: inserted runner_path/gate_path before existence check.")
