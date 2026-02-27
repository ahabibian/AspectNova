from __future__ import annotations

def normalize_stage(name: str) -> str:
    n = (name or "").strip()
    # runnerÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢contract id aliases (ADR-006)
    aliases = {
        "evidence": "evidence_pack",
        "owner": "owner_enricher",
        "owner_report": "owner_enricher",
    }
    return aliases.get(n, n)

import json
import sys
from pathlib import Path

def normalize_stage(name: str) -> str:
    n = (name or "").strip()
    # runnerÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢contract id aliases (ADR-006)
    aliases = {
        "evidence": "evidence_pack",
        "owner": "owner_enricher",
        "owner_report": "owner_enricher",
    }
    return aliases.get(n, n)

try:
    import yaml  # PyYAML
except Exception as e:
    yaml = None

def normalize_stage(name: str) -> str:
    n = (name or "").strip()
    aliases = {
        "evidence": "evidence_pack",
        "owner": "owner_enricher",
        "owner_report": "owner_enricher",
    }
    return aliases.get(n, n)
def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))

def _write_json(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))

def _load_contracts(p: Path) -> dict:
    if yaml is None:
        return {
            "status": "FAIL",
            "where": "verify_contracts",
            "reason": "missing_dependency",
            "detail": "PyYAML is not available (import yaml failed). Install pyyaml.",
            "contracts_path": str(p),
        }
    data = yaml.safe_load(p.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or "stages" not in data:
        return {
            "status": "FAIL",
            "where": "verify_contracts",
            "reason": "invalid_contracts_format",
            "contracts_path": str(p),
        }
    return data

def _evidence_dir(run_id: str) -> Path:
    return Path("runs") / run_id / "output" / "evidence"

def _output_dir(run_id: str) -> Path:
    return Path("runs") / run_id / "output"

def _read_executed_stages_from_log(run_id: str) -> tuple[list[str], str | None]:
    log_path = _evidence_dir(run_id) / "pipeline.log.json"
    if not log_path.exists():
        return [], None
    try:
        entries = _read_json(log_path)
        stages: list[str] = []
        if isinstance(entries, list):
            for it in entries:
                if not isinstance(it, dict):
                    continue

                runner = str(it.get("runner") or "")
                if runner.startswith("run_") and runner.endswith(".py"):
                    # run_x_stage.py -> x (rough)
                    name = runner.replace("run_", "").replace("_stage.py", "").replace(".py", "")
                    if name:
                        stages.append(normalize_stage(name))

                # also allow explicit stage if present
                if it.get("stage"):
                    stages.append(normalize_stage(str(it["stage"])))
        stages = sorted(set([s for s in stages if s]))
        # drop legacy stage id after manifest split (manifest_pre/manifest_post)
        stages = [s for s in stages if s != "manifest"]
        return stages, str(log_path).replace("/", "\\")
    except Exception:
        return [], str(log_path).replace("/", "\\")


def _stage_base_dir(run_id: str, base: str) -> Path:
    base = (base or "").strip().lower()
    if base == "output":
        return _output_dir(run_id)
    # default evidence
    return _evidence_dir(run_id)

def verify_run(run_id: str, contracts_path: Path) -> tuple[dict, int]:
    contracts_path = contracts_path if contracts_path else (Path("contracts") / "stage_contracts.v2.yml")
    if not contracts_path.exists():
        out = {
            "status": "FAIL",
            "where": "verify_contracts",
            "reason": "missing_contracts_file",
            "contracts_path": str(contracts_path).replace("/", "\\"),
        }
        return out, 2

    contracts = _load_contracts(contracts_path)
    if contracts.get("status") == "FAIL":
        return contracts, 2

    defaults = (contracts.get("defaults") or {}) if isinstance(contracts.get("defaults"), dict) else {}
    default_base = str(defaults.get("base") or "evidence")

    executed, executed_src = _read_executed_stages_from_log(run_id)

    # index contracts by id
    stage_defs = contracts.get("stages") or []
    index: dict[str, dict] = {}
    for s in stage_defs:
        if isinstance(s, dict) and s.get("id"):
            index[str(s["id"])] = s

    unknown_executed = [s for s in executed if s not in index]

    # only verify stages that were executed (if log exists), else verify all stages in contracts
    verify_list = executed if executed else list(index.keys())

    results = []
    missing_total = 0

    for sid in verify_list:
        sdef = index.get(sid)
        if not isinstance(sdef, dict):
            continue

        base = str(sdef.get("base") or default_base)
        base_dir = _stage_base_dir(run_id, base)

        outs = sdef.get("outputs") or {}
        canon = (outs.get("canonical") or []) if isinstance(outs, dict) else []
        opt = (outs.get("optional") or []) if isinstance(outs, dict) else []

        expected = []
        for x in canon:
            if isinstance(x, str) and x.strip():
                expected.append(x.strip())

        present = []
        missing = []
        for rel in expected:
            p = base_dir / rel
            if p.exists():
                present.append(rel)
            else:
                missing.append(rel)

        missing_total += len(missing)

        results.append({
            "stage": sid,
            "base": base,
            "base_dir": str(base_dir).replace("/", "\\"),
            "status": "PASS" if len(missing) == 0 else "FAIL",
            "present": present,
            "missing": missing,
            "canonical_expected": expected,
            "optional_defined": [x for x in opt if isinstance(x, str)],
        })

    out = {
        "status": "PASS" if missing_total == 0 and len(unknown_executed) == 0 else "FAIL",
        "run_id": run_id,
        "contracts_source": str(contracts_path).replace("/", "\\"),
        "executed_stages_source": executed_src,
        "executed_stages": executed,
        "unknown_executed_stages": unknown_executed,
        "missing_total": missing_total,
        "stages": results,
    }
    return out, (0 if out["status"] == "PASS" else 1)

def main() -> int:
    if len(sys.argv) < 2:
        _write_json({"status":"FAIL","error":"usage","example":"python .\\tools\\verify_contracts.py <run_id> [contracts_path]"})
        return 2
    run_id = sys.argv[1]
    contracts_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else (Path("contracts") / "stage_contracts.v2.yml")
    out, code = verify_run(run_id, contracts_path)
    _write_json(out)
    return code

if __name__ == "__main__":
    raise SystemExit(main())