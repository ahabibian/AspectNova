from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def safe_int(v: Any, default: int = 0) -> int:
    try:
        n = int(v)
        return n if n >= 0 else default
    except Exception:
        return default


def risk_rank(r: str) -> int:
    # higher is riskier
    return {"low": 1, "medium": 2, "high": 3}.get(r, 3)


def build_summary(targets: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts_action = {"DELETE": 0, "ARCHIVE": 0, "MOVE": 0, "NOOP": 0}
    counts_category = {"ephemeral": 0, "temp": 0, "derived": 0, "ambiguous": 0}
    total_size = 0
    delete_size = 0
    largest = 0

    max_risk = "low"
    any_medium_plus = False

    for t in targets:
        act = t.get("action", "NOOP")
        cat = t.get("category", "ambiguous")
        counts_action[act] = counts_action.get(act, 0) + 1
        counts_category[cat] = counts_category.get(cat, 0) + 1

        sz = safe_int((t.get("stats") or {}).get("size_bytes", 0), 0)
        total_size += sz
        if sz > largest:
            largest = sz

        if act == "DELETE":
            delete_size += sz

        r = t.get("risk", "high")
        if risk_rank(r) > risk_rank(max_risk):
            max_risk = r
        if risk_rank(r) >= risk_rank("medium") and act in ("DELETE", "ARCHIVE", "MOVE"):
            any_medium_plus = True

    # Conservative estimate: only DELETE counts as immediate savings
    estimated_savings_bytes = delete_size

    return {
        "targets_total": len(targets),
        "by_action": counts_action,
        "by_category": counts_category,
        "total_bytes_in_scope": total_size,
        "estimated_savings_bytes": estimated_savings_bytes,
        "largest_target_bytes": largest,
        "max_risk": max_risk,
        "requires_approval": bool(any_medium_plus),
    }


def propose_policy_decision(summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    اینجا هنوز policy engine کامل نداریم، ولی proposal باید decision معنادار داشته باشه:
    - risk_bucket
    - allow_execute
    - requires_approval
    - confidence + reasons
    """
    max_risk = summary["max_risk"]
    requires_approval = summary["requires_approval"]

    # Risk bucket ساده و قابل دفاع (بعداً policy engine واقعی جایگزین می‌شود)
    if max_risk == "low":
        bucket = "A"
        confidence = 0.86
    elif max_risk == "medium":
        bucket = "B"
        confidence = 0.78
    else:
        bucket = "C"
        confidence = 0.62

    allow_execute = (bucket in ("A", "B"))  # C فقط با override
    reasons = []
    reasons.append(f"max_risk={max_risk}")
    if requires_approval:
        reasons.append("approval_required_due_to_medium_or_higher_risk_targets")

    return {
        "policy_id": "default.cleanup.real.v1",
        "risk_bucket": bucket,
        "allow_execute": allow_execute,
        "requires_approval": requires_approval,
        "confidence": confidence,
        "reasons": reasons,
    }


def normalize_targets_for_proposal(targets_in: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    خروجی proposal باید ساده‌تر و audit-friendly باشد (نه تمام evidence scan).
    ولی باید traceability نگه داریم: matched_rule + confidence + rationale + size.
    """
    out: List[Dict[str, Any]] = []
    for t in targets_in:
        stats = t.get("stats") or {}
        out.append({
            "path": t.get("path"),
            "action": t.get("action"),
            "category": t.get("category"),
            "risk": t.get("risk"),
            "matched_rule": t.get("matched_rule"),
            "confidence": t.get("confidence"),
            "rationale": t.get("rationale"),
            "size_bytes": safe_int(stats.get("size_bytes", 0), 0),
            "kind": stats.get("kind"),
            "proposed_destination": t.get("proposed_destination"),  # only for ARCHIVE/MOVE
            "tags": t.get("tags", []),
        })
    return out


def build_cleanup_proposal_v3(
    cleanup_targets_path: Path,
    output_path: Path,
    proposal_id: str | None,
) -> Dict[str, Any]:
    ct = load_json(cleanup_targets_path)

    if ct.get("schema_id") != "aspectnova.cleanup_targets" or ct.get("schema_version") != "v1":
        raise ValueError("Input is not aspectnova.cleanup_targets v1")

    root = ct.get("root", "")
    src = ct.get("source", {})
    targets = ct.get("targets", [])

    if not isinstance(targets, list):
        raise ValueError("cleanup_targets.targets must be a list")

    # proposal should only include actionable items + keep NOOP optionally for transparency
    # We'll include NOOP too (orgs like seeing what was excluded by logic)
    summary = build_summary(targets)
    policy_decision = propose_policy_decision(summary)

    normalized_targets = normalize_targets_for_proposal(targets)

    proposal = {
        "schema_id": "aspectnova.cleanup_proposal",
        "schema_version": "v3",
        "generated_at": utc_now_iso(),
        "proposal_id": proposal_id or f"cleanup-proposal-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "root": root,
        "source": {
            "cleanup_targets": str(cleanup_targets_path),
            "scan_result_canonical": src.get("scan_result_canonical"),
            "scan_payload": src.get("scan_payload"),
        },
        "policy_decision": policy_decision,
        "summary": summary,
        "targets": normalized_targets,
        "notes": [
            "Estimated savings is conservative (DELETE-only).",
            "ARCHIVE/MOVE actions preserve rollback via .aspectnova_archive/${plan_key}/...",
        ]
    }

    write_json(output_path, proposal)
    return proposal


def main() -> int:
    ap = argparse.ArgumentParser(description="AspectNova: Build cleanup proposal v3 from cleanup_targets v1")
    ap.add_argument("--targets", required=True, help="Path to out/cleanup_targets.v1.json")
    ap.add_argument("--out", required=True, help="Output path for out/cleanup_proposal.v3.real.json")
    ap.add_argument("--proposal-id", default=None, help="Optional proposal_id")
    args = ap.parse_args()

    proposal = build_cleanup_proposal_v3(
        cleanup_targets_path=Path(args.targets),
        output_path=Path(args.out),
        proposal_id=args.proposal_id,
    )

    s = proposal["summary"]
    pd = proposal["policy_decision"]
    print(
        f"[OK] wrote {args.out} | targets={s['targets_total']} "
        f"| est_savings_bytes={s['estimated_savings_bytes']} "
        f"| risk_bucket={pd['risk_bucket']} | allow_execute={pd['allow_execute']} | requires_approval={pd['requires_approval']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
