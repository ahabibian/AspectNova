from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _fmt_num(x: Any, digits: int = 5) -> str:
    try:
        v = float(x)
        return f"{v:.{digits}f}"
    except Exception:
        return "0.00000"


def _as_bool(x: Any) -> bool:
    return bool(x) if isinstance(x, bool) else str(x).lower() in ("1", "true", "yes", "y", "on")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("execution_report_json", help="Input: execution_report.v1*.json")
    ap.add_argument("out_report_json", help="Output: report.v1.json (presentation)")
    ap.add_argument("out_report_md", help="Output: report.v1.md (human readable)")
    ap.add_argument("--strict", action="store_true", help="Fail on missing expected keys.")
    args = ap.parse_args()

    r = _read_json(args.execution_report_json)

    # Basic validation (lightweight)
    schema_version = r.get("schema_version", "")
    if args.strict and not str(schema_version).endswith(".execution_report.v1"):
        raise SystemExit(f"Unexpected schema_version: {schema_version}")

    meta = r.get("meta") or {}
    plan = r.get("plan") or {}
    policy = r.get("policy") or {}
    summary = r.get("summary") or {}
    totals = (summary.get("totals") or {})

    results: List[Dict[str, Any]] = r.get("results") or []
    if args.strict and not results:
        raise SystemExit("execution_report has no results[]")

    # Build UI-friendly rows
    rows: List[Dict[str, Any]] = []
    for item in results:
        savings = item.get("projected_savings") or {}
        target = item.get("target") or {}

        rows.append(
            {
                "command_id": item.get("command_id"),
                "type": item.get("type"),
                "target_scope": target.get("scope"),
                "target_ref": target.get("ref"),
                "decision": item.get("decision"),
                "dry_run": _as_bool(item.get("dry_run")),
                "risk_level": item.get("risk_level"),
                "confidence": float(item.get("confidence") or 0.0),
                "savings": {
                    "energy_kwh_per_month": float(savings.get("energy_kwh_per_month") or 0.0),
                    "co2_g_per_month": float(savings.get("co2_g_per_month") or 0.0),
                    "storage_tb_per_month": float(savings.get("storage_tb_per_month") or 0.0),
                },
                "message": item.get("message") or "",
            }
        )

    out = {
        "schema_id": "aspectnova.report",
        "schema_version": "aspectnova.report.v1",
        "generated_at": _utc_now_iso(),
        "source_execution_report": {
            "schema_version": schema_version,
            "trace_id": (meta.get("trace_id") or ""),
        },
        "context": {
            "mode": meta.get("mode"),
            "policy_profile": policy.get("profile"),
            "proposal_id": (plan.get("source") or {}).get("proposal_id"),
            "scan_id": (plan.get("source") or {}).get("scan_id"),
            "plan_key": (plan.get("idempotency") or {}).get("plan_key"),
        },
        "summary": {
            "total": int(summary.get("total") or 0),
            "will_execute": int(summary.get("will_execute") or 0),
            "blocked_policy": int(summary.get("blocked_policy") or 0),
            "skipped_noop": int(summary.get("skipped_noop") or 0),
            "errors": int(summary.get("errors") or 0),
            "totals": {
                "energy_kwh_per_month": float(totals.get("energy_kwh_per_month") or 0.0),
                "co2_g_per_month": float(totals.get("co2_g_per_month") or 0.0),
                "storage_tb_per_month": float(totals.get("storage_tb_per_month") or 0.0),
            },
        },
        "items": rows,
    }

    # Markdown report (clean + readable)
    title = "AspectNova Cleanup Report"
    mode = meta.get("mode", "UNKNOWN")
    profile = policy.get("profile", "default")
    proposal_id = (plan.get("source") or {}).get("proposal_id", "")
    scan_id = (plan.get("source") or {}).get("scan_id", "")
    plan_key = (plan.get("idempotency") or {}).get("plan_key", "")
    trace_id = meta.get("trace_id", "")

    md_lines = []
    md_lines.append(f"# {title}")
    md_lines.append("")
    md_lines.append(f"- Generated at: `{out['generated_at']}`")
    md_lines.append(f"- Mode: `{mode}`")
    md_lines.append(f"- Policy: `{profile}`")
    md_lines.append(f"- Proposal ID: `{proposal_id}`")
    md_lines.append(f"- Scan ID: `{scan_id}`")
    md_lines.append(f"- Plan key: `{plan_key}`")
    md_lines.append(f"- Trace ID: `{trace_id}`")
    md_lines.append("")
    md_lines.append("## Summary")
    md_lines.append("")
    md_lines.append(f"- Total commands: **{out['summary']['total']}**")
    md_lines.append(f"- Will execute: **{out['summary']['will_execute']}**")
    md_lines.append(f"- Blocked (policy): **{out['summary']['blocked_policy']}**")
    md_lines.append(f"- Skipped (noop): **{out['summary']['skipped_noop']}**")
    md_lines.append(f"- Errors: **{out['summary']['errors']}**")
    md_lines.append("")
    md_lines.append("### Totals (per month)")
    md_lines.append("")
    md_lines.append(f"- Energy (kWh): **{_fmt_num(out['summary']['totals']['energy_kwh_per_month'])}**")
    md_lines.append(f"- CO2 (g): **{_fmt_num(out['summary']['totals']['co2_g_per_month'])}**")
    md_lines.append(f"- Storage (TB): **{_fmt_num(out['summary']['totals']['storage_tb_per_month'])}**")
    md_lines.append("")
    md_lines.append("## Items")
    md_lines.append("")
    md_lines.append("| # | Type | Decision | Risk | Confidence | Target | Energy kWh/mo | CO2 g/mo | Storage TB/mo | Message |")
    md_lines.append("|---:|------|----------|------|-----------:|--------|--------------:|---------:|--------------:|---------|")

    for i, it in enumerate(out["items"], start=1):
        tgt = f"{it['target_scope']}:{it['target_ref']}"
        md_lines.append(
            f"| {i} | {it['type']} | {it['decision']} | {it['risk_level']} | {it['confidence']:.2f} | "
            f"{tgt} | {_fmt_num(it['savings']['energy_kwh_per_month'])} | {_fmt_num(it['savings']['co2_g_per_month'])} | "
            f"{_fmt_num(it['savings']['storage_tb_per_month'])} | {it['message'].replace('|','/')} |"
        )

    _write_json(args.out_report_json, out)
    _write_text(args.out_report_md, "\n".join(md_lines) + "\n")

    print(f"[render_report_v1] OK -> wrote: {args.out_report_json}")
    print(f"[render_report_v1] OK -> wrote: {args.out_report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
