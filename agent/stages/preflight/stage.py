from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text_bom_safe(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


def _write_text_utf8(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")  # UTF-8 no BOM


def _read_json_bom_safe(p: Path):
    return json.loads(_read_text_bom_safe(p))


def _write_json_utf8(p: Path, obj) -> None:
    _write_text_utf8(p, json.dumps(obj, ensure_ascii=False, indent=2))


def _apply_placeholders(s: str, run_id: str) -> str:
    return s.replace("{RUN_ID}", run_id)


class PreflightStage:
    """
    Enterprise reliability preflight (registry-driven):
      - normalize policies to UTF-8 no BOM (idempotent)
      - apply compatibility rules from tools/compat_registry.json
      - emit preflight.report.json with metrics
    """

    def run(
        self,
        run_id: str,
        runs_dir: Path = Path("runs"),
        policies_dir: Path = Path("policies"),
        registry_path: Path = Path("tools/compat_registry.json"),
    ) -> dict:
        O = Path(".") / runs_dir / run_id / "output"
        E = O / "evidence"
        E.mkdir(parents=True, exist_ok=True)

        fixes = []
        warnings = []
        errors = []
        aliases_created = 0

        # 1) Normalize all *.policy.json (remove BOM by rewriting canonical JSON)
        if policies_dir.exists():
            for pol in policies_dir.glob("*.policy.json"):
                try:
                    obj = _read_json_bom_safe(pol)
                    _write_json_utf8(pol, obj)
                    fixes.append({"kind": "policy_utf8_nobom", "path": str(pol).replace("/", "\\")})
                except Exception as ex:
                    warnings.append({"type": "policy_normalize_failed", "path": str(pol).replace("/", "\\"), "error": str(ex)})

        # 2) Compatibility registry (optional)
        reg_obj = None
        if registry_path.exists():
            try:
                reg_obj = _read_json_bom_safe(registry_path)
            except Exception as ex:
                errors.append({"type": "compat_registry_read_failed", "path": str(registry_path).replace("/", "\\"), "error": str(ex)})

        if reg_obj:
            rules = reg_obj.get("rules") or []
            for r in rules:
                rid = r.get("id")
                try:
                    when_missing = _apply_placeholders(str(r.get("when_missing") or ""), run_id)
                    derive_from = _apply_placeholders(str(r.get("derive_from") or ""), run_id)
                    action = (r.get("action") or "").strip()

                    if not when_missing or not derive_from or not action:
                        warnings.append({"type": "compat_rule_invalid", "id": rid, "detail": r})
                        continue

                    missing_path = Path(when_missing)
                    src_path = Path(derive_from)

                    if missing_path.exists():
                        continue

                    if not src_path.exists():
                        warnings.append({"type": "compat_rule_source_missing", "id": rid, "source": str(src_path).replace("/", "\\")})
                        continue

                    if action == "copy_text_utf8":
                        _write_text_utf8(missing_path, _read_text_bom_safe(src_path))
                        fixes.append({
                            "kind": "compat_alias_emit",
                            "id": rid,
                            "from": str(src_path).replace("/", "\\"),
                            "to": str(missing_path).replace("/", "\\"),
                        })
                        aliases_created += 1
                    else:
                        warnings.append({"type": "compat_rule_unknown_action", "id": rid, "action": action})
                except Exception as ex:
                    errors.append({"type": "compat_rule_apply_failed", "id": rid, "error": str(ex)})

        status = "PASS" if not errors else "FAIL"
        report = {
            "stage": "preflight",
            "schema_version": "1.1.0",
            "run_id": run_id,
            "generated_at_utc": _utc_now(),
            "status": status,
            "fixes": fixes,
            "warnings": warnings,
            "errors": errors,
            "metrics": {"aliases_created": aliases_created},
            "paths": {"output": str(O).replace("/", "\\"), "evidence": str(E).replace("/", "\\")},
        }

        _write_json_utf8(E / "preflight.report.json", report)
        return report
