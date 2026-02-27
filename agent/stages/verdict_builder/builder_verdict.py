import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

def _now_utc():
    return datetime.now(timezone.utc).isoformat()

def build_verdict(evidence_pack_path: Path, out_path: Path, run_id: str):
    pack = json.loads(evidence_pack_path.read_text(encoding="utf-8"))
    nodes = pack.get("nodes") or []
    edges = pack.get("edges") or []

    # --- pull owner observations
    owner_obs = [
        n for n in nodes
        if n.get("type") == "observation" and n.get("subtype") == "win_sd_owner_lookup"
    ]

    total = len(owner_obs)
    ok_obs = [o for o in owner_obs if (o.get("properties") or {}).get("ok") is True]
    fail_obs = [o for o in owner_obs if (o.get("properties") or {}).get("ok") is False]

    # --- fail breakdown
    fail_codes = Counter((o.get("properties") or {}).get("error_code") for o in fail_obs)
    fail_rate = (len(fail_obs) / total) if total else 1.0

    # --- owner distribution (only OK)
    owners = [(o.get("properties") or {}).get("owner") for o in ok_obs]
    owners = [x for x in owners if x]
    top_owners = [{"owner": k, "count": v} for k, v in Counter(owners).most_common(20)]

    # --- findings
    findings = []

    # Access denied is always high severity in org contexts
    access_denied = int(fail_codes.get("access_denied", 0) or 0)
    if access_denied > 0:
        findings.append({
            "id": "F-OWNER-ACCESS-DENIED",
            "title": "Owner lookup access denied encountered",
            "severity": "HIGH",
            "metric": {"access_denied": access_denied},
            "samples": [
                (o.get("properties") or {}).get("error_detail")
                for o in fail_obs
                if (o.get("properties") or {}).get("error_code") == "access_denied"
            ][:25],
            "recommendation": "Run with sufficient privileges or exclude protected paths; verify OneDrive/enterprise policy constraints."
        })

    # Not found is low severity if rare; still report samples
    not_found = int(fail_codes.get("not_found", 0) or 0)
    if not_found > 0:
        findings.append({
            "id": "F-OWNER-NOT-FOUND",
            "title": "Some paths not found at enrichment time",
            "severity": "LOW",
            "metric": {"not_found": not_found},
            "samples": [
                (o.get("properties") or {}).get("error_detail")
                for o in fail_obs
                if (o.get("properties") or {}).get("error_code") == "not_found"
            ][:25],
            "recommendation": "Usually caused by moved/deleted files between scan and enrich. Consider snapshotting, or re-scan before enrich in strict runs."
        })

    other_error = int(fail_codes.get("other_error", 0) or 0)
    if other_error > 0:
        findings.append({
            "id": "F-OWNER-OTHER-ERROR",
            "title": "Unexpected errors during owner lookup",
            "severity": "MEDIUM",
            "metric": {"other_error": other_error},
            "samples": [
                (o.get("properties") or {}).get("error_detail")
                for o in fail_obs
                if (o.get("properties") or {}).get("error_code") == "other_error"
            ][:25],
            "recommendation": "Inspect error_detail; improve classifier; add retry/backoff where appropriate."
        })

    # --- overall status heuristic (policy will enforce hard thresholds)
    status = "PASS"
    if access_denied > 0:
        status = "FAIL"
    # if fail_rate is huge, fail (policy also gates)
    if fail_rate > 0.01:
        status = "FAIL"

    verdict = {
        "contract_version": "verdict/1.0",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at_utc": _now_utc(),
        "inputs": {
            "evidence_pack": str(evidence_pack_path)
        },
        "summary": {
            "status": status,
            "totals": {
                "owner_obs_total": total,
                "owner_ok": len(ok_obs),
                "owner_fail": len(fail_obs),
                "owner_fail_rate": fail_rate
            },
            "fail_by_code": dict(fail_codes),
            "top_owners": top_owners
        },
        "graph_stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "edge_types_top": dict(Counter((e.get("type") for e in edges)).most_common(20)),
        },
        "findings": findings
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    return verdict
