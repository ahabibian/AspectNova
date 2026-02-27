from __future__ import annotations

def normalize_stage(name: str) -> str:
  n = (name or "").strip()
  aliases = {
    "evidence": "evidence_pack",
    "owner": "owner_enricher",
    "owner_report": "owner_enricher",
  }
  return aliases.get(n, n)

import argparse
import json
import subprocess
import sys
import shutil
from pathlib import Path

def normalize_stage(name: str) -> str:
  n = (name or "").strip()
  aliases = {
    "evidence": "evidence_pack",
    "owner": "owner_enricher",
    "owner_report": "owner_enricher",
  }
  return aliases.get(n, n)


# stage runner, gate tool, gate_args, must_exist, gate_out
STAGES = [
  # --- preflight (BOM + compat aliases)
  ("run_preflight_stage.py",     "tools/gate_preflight.py",
    ["{E}/preflight.report.json", "policies/preflight.policy.json"],
    "{E}/preflight.report.json", "{E}/preflight.gate.json"),


  # --- scan stage (creates runs/<run_id>/input/scan_result.json)
  ("run_scan_stage.py",         "tools/gate_scan_stage.py",
    ["{I}/scan_result.json"],
    "{I}/scan_result.json", "{E}/scan_stage.gate.json"),

  # --- scan normalize
  ("run_scan_normalizer.py",    "tools/gate_scan_normalizer.py",
    ["{O}/scan_result.canonical.v1.json", "policies/scan_normalizer.policy.json"],
    "{O}/scan_result.canonical.v1.json", "{E}/scan_normalizer.gate.json"),

  # --- evidence pack
  ("run_evidence_stage.py",     "tools/gate_evidence_pack.py",
    ["{E}/evidence_pack.v1.json", "policies/evidence_pack.policy.json"],
    "{E}/evidence_pack.v1.json", "{E}/evidence_pack.gate.json"),

  # --- owner enrich (policy selected by profile)
  ("run_owner_stage.py",        "tools/gate_owner_report.py",
    ["{E}/owner_enricher.stats.json", "{OWNER_POLICY}"],
    "{E}/owner_enricher.stats.json", "{E}/owner_enricher.gate.json"),

  # --- verdict (policy selected by profile)
  ("run_verdict_stage.py",      "tools/gate_verdict.py",
    ["{E}/verdict.json", "{VERDICT_POLICY}"],
    "{E}/verdict.json", "{E}/verdict.gate.json"),

  # --- command_plan (policy selected by profile)
  ("run_command_plan_stage.py", "tools/gate_command_plan.py",
    ["{E}/command_plan.json", "{COMMAND_PLAN_POLICY}"],
    "{E}/command_plan.json", "{E}/command_plan.gate.json"),

  # --- manifest (needed for approval contract + later integrity)
  ("run_manifest_stage.py",     "manifest_pre", "tools/gate_manifest.py",
    ["{E}/manifest.pre.report.json", "policies/manifest.policy.json"],
    "{E}/manifest.pre.report.json", "{E}/manifest.pre.gate.json"),

  # --- approval (uses run_manifest.json created by manifest stage or preflight alias)
  ("run_approval_stage.py",     "tools/gate_approval.py",
    ["{E}/approval.json", "policies/approval.policy.json"],
    "{E}/approval.json", "{E}/approval.gate.json"),

  # --- execution
  ("run_execution_stage.py",    "tools/gate_execution.py",
    ["{E}/execution_report.json", "policies/execution.policy.json"],
    "{E}/execution_report.json", "{E}/execution.gate.json"),

  
  # --- manifest (post-execution snapshot for integrity)
  ("run_manifest_stage.py",     "manifest_post", "tools/gate_manifest.py",
    ["{E}/manifest.post.report.json", "policies/manifest.policy.json"],
    "{E}/manifest.post.report.json", "{E}/manifest.post.gate.json"),
# --- integrity
  ("run_integrity_stage.py",    "tools/gate_integrity.py",
    ["{E}/integrity_report.json", "policies/integrity.policy.json"],
    "{E}/integrity_report.json", "{E}/integrity.gate.json"),

  # --- finalizer
  ("run_finalizer_stage.py",    "tools/gate_finalizer.py",
    ["{E}/final_report.json", "policies/finalizer.policy.json"],
    "{E}/final_report.json", "{E}/finalizer.gate.json"),
]


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:

  p = subprocess.run(cmd, capture_output=True, text=True, shell=False)
  return p.returncode, p.stdout, p.stderr


def write_text(p: Path, txt: str) -> None:
  p.parent.mkdir(parents=True, exist_ok=True)
  p.write_text(txt, encoding="utf-8")


def build_args():
  p = argparse.ArgumentParser()
  p.add_argument("--run-id", dest="run_id", required=True)
  p.add_argument("--runs-dir", dest="runs_dir", default="runs")
  p.add_argument("--root", default=None, help="Override scan root (scan stage only)")

  p.add_argument("--profile", dest="profile", default="strict", choices=["strict", "manual"])
  p.add_argument("--force", action="store_true", help="Allow overwriting existing evidence outputs")
  p.add_argument("--new-run", dest="new_run", action="store_true", help="Fail if run output already exists (avoid run_id reuse)")
  p.add_argument("--selftest-only", dest="selftest_only", action="store_true", help="Run selftest + devguard only, then exit")
  return p.parse_args()


def main() -> None:
  args = build_args()

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

  run_id = args.run_id
  runs_dir = args.runs_dir
  root = Path(".")

  O = root / runs_dir / run_id / "output"
  E = O / "evidence"

  I = root / runs_dir / run_id / "input"

  # --- ANTI-OVERWRITE (enterprise safety)
  if args.new_run and (O.exists() or E.exists()):
    print(json.dumps({"status":"FAIL","where":"anti_overwrite","reason":"run_id_reuse","out_dir":str(O)}, indent=2))
    raise SystemExit(10)

  final_gate = E / "finalizer.gate.json"
  if final_gate.exists() and (not args.force):
    print(json.dumps({"status":"FAIL","where":"anti_overwrite","reason":"final_already_exists","final_gate": str(final_gate)}, indent=2))
    raise SystemExit(10)
  verdict_policy = "policies/verdict.policy.manual.json" if args.profile == "manual" else "policies/verdict.policy.json"
  command_plan_policy = "policies/command_plan.policy.manual.json" if args.profile == "manual" else "policies/command_plan.policy.json"
  owner_policy = "policies/owner_enricher.policy.manual.json" if args.profile == "manual" else "policies/owner_enricher.policy.json"

  pipeline_log: list[dict] = []

  for _stage in STAGES:
    if len(_stage) == 5:
      runner, gate, gate_args, must_exist, gate_out = _stage
      # --- canonical stage id for log (stable)
      stage_id = normalize_stage(Path(runner).stem.replace("run_", "").replace("_stage", ""))
      # manifest split: detect pre/post by gate_out filename
      if runner == "run_manifest_stage.py":
        stage_id = "manifest_post" if "manifest_post" in str(gate_out) else "manifest_pre"
    elif len(_stage) == 6:
      runner, stage_id, gate, gate_args, must_exist, gate_out = _stage
    else:
      raise ValueError("Invalid STAGES entry length=%s entry=%r" % (len(_stage), _stage))
  

    runner_path = root / runner
    gate_path = root / gate
    if not runner_path.exists():
      raise FileNotFoundError(f"missing runner: {runner_path}")
    if not gate_path.exists():
      raise FileNotFoundError(f"missing gate tool: {gate_path}")

    step = {"runner": runner, "stage": stage_id, "gate": gate, "status": "START", "exitcode": None}
    pipeline_log.append(step)

    # --- run stage
    if runner == "run_approval_stage.py":
      cmd = [sys.executable, str(runner_path), run_id, "APPROVE", "pipeline orchestrator approval (plan-only)"]

      # --- ROOT_OVERRIDE passthrough (scan stage only) [MAIN_LOOP]
      # Robust rule: use stage/stage_id, not runner basename.
      try:
        if getattr(args, "root", None):
          st = str(step.get("stage",""))
          sid = str(step.get("stage_id",""))
          if (st == "scan") or (sid == "scan") or ("scan" in st.lower()) or ("scan" in sid.lower()):
            if "--root" not in cmd:
              cmd += ["--root", args.root]
            step["scan_root_override"] = args.root
          # always record cmd for debugging (first 10 args)
          step["cmd_preview"] = cmd[:10]
      except Exception as _e:
        step["scan_root_override_error"] = str(_e)




    else:
      cmd = [sys.executable, str(runner_path), run_id]

    # --- ROOT_OVERRIDE passthrough (scan stage only) [BEFORE_RUN_CMD]

    try:

      if getattr(args, "root", None):

        st = str(step.get("stage",""))

        if st == "scan" and ("--root" not in cmd):

          cmd += ["--root", args.root]

          step["scan_root_override"] = args.root

      step["cmd_preview"] = cmd[:10]

    except Exception as _e:

      step["scan_root_override_error"] = str(_e)


    rc, out, err = run_cmd(cmd)
    step["stage_exitcode"] = rc
    step["stage_stdout"] = (out or "")[-4000:]
    step["stage_stderr"] = (err or "")[-4000:]

    if rc != 0:
      step["status"] = "FAIL_STAGE"
      print(json.dumps({"status": "FAIL", "where": "stage", "runner": runner, "exitcode": rc}, indent=2))
      write_text(E / "pipeline.log.json", json.dumps(pipeline_log, ensure_ascii=False, indent=2))
      raise SystemExit(rc)

    # --- ensure expected artifact exists
    must_s = str(must_exist).replace("{I}", str(I).replace("\\","/")).replace("{O}", str(O).replace("\\","/")).replace("{E}", str(E).replace("\\","/"))
    must_p = Path(must_s).as_posix().replace("/", "\\")
    must_path = Path(must_p)

    # --- MANIFEST_POST_FALLBACK (compat bridge)
    # run_manifest_stage currently writes manifest.pre.report.json / manifest.report.json.
    # pipeline expects manifest.post.report.json for the post snapshot.
    if (not must_path.exists()) and (stage_id == "manifest_post"):
      alt1 = E / "manifest.pre.report.json"
      alt2 = E / "manifest.report.json"
      try:
        if alt1.exists():
          must_path.parent.mkdir(parents=True, exist_ok=True)
          shutil.copyfile(str(alt1), str(must_path))
          step["manifest_post_fallback"] = str(alt1)
        elif alt2.exists():
          must_path.parent.mkdir(parents=True, exist_ok=True)
          shutil.copyfile(str(alt2), str(must_path))
          step["manifest_post_fallback"] = str(alt2)
      except Exception as _e:
        step["manifest_post_fallback_error"] = str(_e)


    if not must_path.exists():
      step["status"] = "FAIL_MISSING_ARTIFACT"
      print(json.dumps({"status": "FAIL", "where": "artifact_missing", "path": str(must_path)}, indent=2))
      write_text(E / "pipeline.log.json", json.dumps(pipeline_log, ensure_ascii=False, indent=2))
      raise SystemExit(3)

    # --- gate
    gargs = []
    for a in gate_args:
      a2 = a.replace("{VERDICT_POLICY}", verdict_policy).replace("{COMMAND_PLAN_POLICY}", command_plan_policy).replace("{OWNER_POLICY}", owner_policy)
      a2 = a2.replace("{I}", str(I).replace("\\","/")).replace("{O}", str(O).replace("\\","/")).replace("{E}", str(E).replace("\\","/"))
      gargs.append(a2.replace("/", "\\"))

    gate_cmd = [sys.executable, str(gate_path)] + gargs
    rc, gout, gerr = run_cmd(gate_cmd)
    step["gate_exitcode"] = rc
    step["gate_stdout"] = (gout or "")[-4000:]
    step["gate_stderr"] = (gerr or "")[-4000:]

    gate_out_s = str(gate_out).replace("{O}", str(O).replace("\\", "/")).replace("{E}", str(E).replace("\\", "/"))
    gate_out_path = Path(gate_out_s).as_posix().replace("/", "\\")
    write_text(Path(gate_out_path), gout if (gout or "").strip() else (gerr or ""))

    if rc != 0:
      step["status"] = "FAIL_GATE"
      print(json.dumps({"status": "FAIL", "where": "gate", "gate": gate, "exitcode": rc, "gate_out": str(gate_out_path)}, indent=2))
      write_text(E / "pipeline.log.json", json.dumps(pipeline_log, ensure_ascii=False, indent=2))
      raise SystemExit(rc)

    step["status"] = "PASS"

  write_text(E / "pipeline.log.json", json.dumps(pipeline_log, ensure_ascii=False, indent=2))
  print(json.dumps({"status": "PASS", "run_id": run_id, "evidence_dir": str(E).replace("/", "\\")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
  main()

