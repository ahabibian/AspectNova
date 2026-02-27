from __future__ import annotations
from pathlib import Path
import sys, json, re

ROOT = Path(__file__).resolve().parents[2]

CRITICAL_NO_BOM = [
  "run_pipeline.py",
  "run_execution_stage.py",
  "run_approval_stage.py",
  "tools/dev/devguard.py",
  "tools/dev/selftest.py",
]

def read_bytes(p: Path) -> bytes:
  return p.read_bytes()

def has_bom(b: bytes) -> bool:
  return b.startswith(b"\xef\xbb\xbf")

def fail(where: str, detail: dict):
  print(json.dumps({"status":"FAIL","where":where, "detail":detail}, ensure_ascii=False, indent=2))
  raise SystemExit(9)

def ok(detail: dict):
  print(json.dumps({"status":"OK","detail":detail}, ensure_ascii=False, indent=2))

def check_no_bom():
  bad = []
  missing = []
  for rel in CRITICAL_NO_BOM:
    p = ROOT / rel
    if not p.exists():
      missing.append(rel)
      continue
    if has_bom(read_bytes(p)):
      bad.append(rel)
  if missing:
    fail("selftest:no_bom", {"missing": missing})
  if bad:
    fail("selftest:no_bom", {"bom_detected": bad})
  return {"bom_detected": 0}

def extract_stages(run_pipeline_text: str):
  # very lightweight parse: ensure STAGES exists and contains key runners
  if "STAGES = [" not in run_pipeline_text:
    fail("selftest:stages", {"reason":"STAGES_not_found"})
  must = [
    "run_preflight_stage.py",
    "run_scan_normalizer.py",
    "run_evidence_stage.py",
    "run_owner_stage.py",
    "run_verdict_stage.py",
    "run_command_plan_stage.py",
    "run_manifest_stage.py",
    "run_approval_stage.py",
    "run_execution_stage.py",
    "run_integrity_stage.py",
    "run_finalizer_stage.py",
  ]
  for m in must:
    if m not in run_pipeline_text:
      fail("selftest:stages", {"reason":"missing_runner_in_STAGES", "missing": m})

  # ensure manifest appears twice (pre + post execution snapshot)
  manifest_count = run_pipeline_text.count("run_manifest_stage.py")
  if manifest_count < 2:
    fail("selftest:stages", {"reason":"manifest_not_twice", "count": manifest_count})

  # ensure devguard gate exists
  if "tools/dev/devguard.py" not in run_pipeline_text:
    fail("selftest:devguard", {"reason":"devguard_call_missing"})

  # ensure anti-overwrite marker exists
  if "ANTI-OVERWRITE" not in run_pipeline_text:
    fail("selftest:anti_overwrite", {"reason":"anti_overwrite_block_missing"})

  return {"manifest_count": manifest_count}

def check_paths_exist():
  must_paths = [
    ROOT / "tools" / "dev" / "devguard.py",
    ROOT / "tools" / "gate_integrity.py",
    ROOT / "tools" / "gate_finalizer.py",
    ROOT / "stages" / "finalizer" / "stage.py",
  ]
  missing = [str(p.relative_to(ROOT)) for p in must_paths if not p.exists()]
  if missing:
    fail("selftest:paths", {"missing": missing})
  return {"paths_ok": True}

def main():
  rp = ROOT / "run_pipeline.py"
  txt = rp.read_text(encoding="utf-8", errors="strict")

  r1 = check_no_bom()
  r2 = check_paths_exist()
  r3 = extract_stages(txt)

  ok({"no_bom": r1, "paths": r2, "stages": r3})

if __name__ == "__main__":
  main()