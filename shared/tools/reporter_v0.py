from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReporterError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ReporterError(f"File not found: {path}")
    try:
        txt = path.read_text(encoding="utf-8")
        return json.loads(txt)
    except json.JSONDecodeError as e:
        raise ReporterError(f"Invalid JSON in {path}: {e}") from e
    except Exception as e:
        raise ReporterError(f"Failed to read {path}: {e}") from e


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _get_action_type(a: Dict[str, Any]) -> str:
    # canonical
    if isinstance(a.get("action_type"), str):
        return a["action_type"]
    # defensive fallbacks
    if isinstance(a.get("type"), str):
        return a["type"]
    if isinstance(a.get("action"), str):
        return a["action"]
    return ""


def _summarize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    kpis = (payload.get("kpis") or {}) if isinstance(payload.get("kpis"), dict) else {}
    eii = (payload.get("eii") or {}) if isinstance(payload.get("eii"), dict) else {}
    scan = (payload.get("scan") or {}) if isinstance(payload.get("scan"), dict) else {}

    return {
        "payload_schema_id": payload.get("schema_id"),
        "payload_schema_version": payload.get("schema_version"),
        "kpis": {
            "files_scanned": kpis.get("files_scanned"),
            "total_size_bytes": kpis.get("total_size_bytes"),
            "energy_kwh_month": kpis.get("energy_kwh_month"),
            "energy_kwh_year": kpis.get("energy_kwh_year"),
            "eii_score_value": kpis.get("eii_score_value"),
            "eii_grade": kpis.get("eii_grade"),
        },
        "scan": {
            "canonical_schema_version": ((scan.get("canonical") or {}) if isinstance(scan.get("canonical"), dict) else {}).get(
                "schema_version"
            )
        },
        "eii": {
            "eii_score": (eii.get("eii_score") or {}) if isinstance(eii.get("eii_score"), dict) else eii.get("eii_score"),
            "energy_impact": eii.get("energy_impact"),
        },
    }


def _summarize_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    decision = policy.get("decision") if isinstance(policy.get("decision"), dict) else {}
    policy_meta = policy.get("policy") if isinstance(policy.get("policy"), dict) else {}
    return {
        "policy_schema_id": policy.get("schema_id"),
        "policy_schema_version": policy.get("schema_version"),
        "policy_id": policy_meta.get("policy_id") or policy.get("policy_id") or decision.get("policy_id"),
        "priority": decision.get("priority"),
        "risk_bucket": decision.get("risk_bucket"),
        "confidence": decision.get("confidence"),
        "rationale": decision.get("rationale"),
    }


def _summarize_execution_report(exec_report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not exec_report:
        return {"present": False}
    summary = exec_report.get("summary") if isinstance(exec_report.get("summary"), dict) else {}
    return {
        "present": True,
        "schema_id": exec_report.get("schema_id"),
        "schema_version": exec_report.get("schema_version"),
        "status": summary.get("status"),
        "total": summary.get("total"),
        "ok": summary.get("ok"),
        "skipped": summary.get("skipped"),
        "blocked": summary.get("blocked"),
        "failed": summary.get("failed"),
        "policy_id": exec_report.get("policy_id"),
    }


def _render_report_md(payload_s: Dict[str, Any], policy_s: Dict[str, Any], exec_s: Dict[str, Any]) -> str:
    k = payload_s.get("kpis") or {}
    lines: List[str] = []
    lines.append("# AspectNova – Cleanup Report (v0)")
    lines.append("")
    lines.append(f"- generated_at: `{_now_iso()}`")
    lines.append(f"- payload: `{payload_s.get('payload_schema_id')}@{payload_s.get('payload_schema_version')}`")
    lines.append(f"- policy: `{policy_s.get('policy_id')}`  (priority={policy_s.get('priority')}, risk={policy_s.get('risk_bucket')}, confidence={policy_s.get('confidence')})")
    lines.append("")
    lines.append("## KPIs")
    lines.append(f"- files_scanned: **{k.get('files_scanned')}**")
    lines.append(f"- total_size_bytes: **{k.get('total_size_bytes')}**")
    lines.append(f"- energy_kwh_month: **{k.get('energy_kwh_month')}**")
    lines.append(f"- energy_kwh_year: **{k.get('energy_kwh_year')}**")
    lines.append(f"- eii_score_value: **{k.get('eii_score_value')}**")
    lines.append(f"- eii_grade: **{k.get('eii_grade')}**")
    lines.append("")
    lines.append("## Policy decision")
    lines.append(f"- policy_id: `{policy_s.get('policy_id')}`")
    lines.append(f"- priority: `{policy_s.get('priority')}`")
    lines.append(f"- risk_bucket: `{policy_s.get('risk_bucket')}`")
    lines.append(f"- confidence: `{policy_s.get('confidence')}`")
    if policy_s.get("rationale"):
        lines.append("")
        lines.append("### Rationale")
        if isinstance(policy_s["rationale"], list):
            for r in policy_s["rationale"]:
                lines.append(f"- {r}")
        else:
            lines.append(str(policy_s["rationale"]))
    lines.append("")
    lines.append("## Execution snapshot")
    if exec_s.get("present"):
        lines.append(f"- status: `{exec_s.get('status')}`")
        lines.append(f"- total: {exec_s.get('total')} | ok: {exec_s.get('ok')} | skipped: {exec_s.get('skipped')} | blocked: {exec_s.get('blocked')} | failed: {exec_s.get('failed')}")
    else:
        lines.append("- (no execution_report.json provided)")
    lines.append("")
    return "\n".join(lines)


def _render_proposal_md(payload_s: Dict[str, Any], policy_s: Dict[str, Any]) -> str:
    k = payload_s.get("kpis") or {}
    lines: List[str] = []
    lines.append("# AspectNova – Cleanup Proposal (v0)")
    lines.append("")
    lines.append(f"- generated_at: `{_now_iso()}`")
    lines.append(f"- policy_id: `{policy_s.get('policy_id')}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"This proposal is generated from scan KPIs and policy decision.")
    lines.append("")
    lines.append("## Observations")
    lines.append(f"- files scanned: **{k.get('files_scanned')}**")
    lines.append(f"- total size: **{k.get('total_size_bytes')} bytes**")
    lines.append(f"- estimated energy impact: **{k.get('energy_kwh_month')} kWh/month**, **{k.get('energy_kwh_year')} kWh/year**")
    lines.append(f"- EII: **{k.get('eii_score_value')}** (grade **{k.get('eii_grade')}**)")
    lines.append("")
    lines.append("## Recommended next actions")
    lines.append("- Review candidate deletions / duplicates / large files (from plan).")
    lines.append("- Run execution steps only after explicit confirmation.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Reporter v0 - generate report/proposal artifacts from execution plan.")
    ap.add_argument("--plan", required=True, help="Path to execution_plan.json")
    ap.add_argument("--payload", required=True, help="Path to scan_payload.json")
    ap.add_argument("--policy", required=True, help="Path to policy_decision.json")
    ap.add_argument("--exec-report", default="", help="Optional path to execution_report.json")
    ap.add_argument("--out", required=True, help="Path to report_artifacts.json (manifest)")
    args = ap.parse_args()

    plan_path = Path(args.plan)
    payload_path = Path(args.payload)
    policy_path = Path(args.policy)
    exec_report_path = Path(args.exec_report) if args.exec_report else None
    out_manifest = Path(args.out)

    plan_doc = _read_json(plan_path)
    payload_doc = _read_json(payload_path)
    policy_doc = _read_json(policy_path)
    exec_doc = _read_json(exec_report_path) if exec_report_path else None

    # Extract report/proposal actions from plan
    plan_list = plan_doc.get("plan") if isinstance(plan_doc.get("plan"), list) else []
    report_actions = [a for a in plan_list if _get_action_type(a) == "report"]
    proposal_actions = [a for a in plan_list if _get_action_type(a) == "proposal"]

    payload_s = _summarize_payload(payload_doc)
    policy_s = _summarize_policy(policy_doc)
    exec_s = _summarize_execution_report(exec_doc)

    # Always generate artifacts if their action types exist in plan
    artifacts: List[Dict[str, Any]] = []

    out_dir = out_manifest.parent
    report_md_path = out_dir / "report.md"
    proposal_md_path = out_dir / "proposal.md"

    if report_actions:
        report_md = _render_report_md(payload_s, policy_s, exec_s)
        _write_text(report_md_path, report_md)
        artifacts.append(
            {
                "artifact_type": "report_md",
                "path": str(report_md_path).replace("\\", "/"),
                "source_action_count": len(report_actions),
            }
        )

    if proposal_actions:
        proposal_md = _render_proposal_md(payload_s, policy_s)
        _write_text(proposal_md_path, proposal_md)
        artifacts.append(
            {
                "artifact_type": "proposal_md",
                "path": str(proposal_md_path).replace("\\", "/"),
                "source_action_count": len(proposal_actions),
            }
        )

    manifest = {
        "schema_id": "report-artifacts",
        "schema_version": "v0",
        "generated_at": _now_iso(),
        "inputs": {
            "plan": str(plan_path).replace("\\", "/"),
            "payload": str(payload_path).replace("\\", "/"),
            "policy": str(policy_path).replace("\\", "/"),
            "execution_report": str(exec_report_path).replace("\\", "/") if exec_report_path else None,
        },
        "policy_id": policy_s.get("policy_id"),
        "artifacts": artifacts,
        "summary": {
            "report_actions": len(report_actions),
            "proposal_actions": len(proposal_actions),
            "artifacts_written": len(artifacts),
        },
    }

    _write_json(out_manifest, manifest)
    print(f"OK -> wrote: {out_manifest}")


if __name__ == "__main__":
    main()
