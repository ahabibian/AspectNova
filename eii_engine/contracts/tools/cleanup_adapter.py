from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


# -------------------------
# Helpers
# -------------------------

def utc_now_z() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def to_num(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def gb_to_bytes_decimal(gb: float) -> int:
    # decimal GB to bytes (1 GB = 1,000,000,000 bytes) for consistency with your GB aggregates
    if gb <= 0:
        return 0
    return int(gb * 1_000_000_000)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_path(p: str) -> str:
    return p.replace("\\", "/").strip("/")


def pick_groups(by_ext_gb: Dict[str, Any], min_group_gb: float) -> List[Dict[str, Any]]:
    pairs: List[Tuple[str, float]] = []
    for ext, gb in (by_ext_gb or {}).items():
        v = to_num(gb, 0.0)
        if v >= min_group_gb and v > 0:
            pairs.append((str(ext), v))
    pairs.sort(key=lambda x: x[1], reverse=True)
    return [{"ext": ext, "group_gb": gb} for ext, gb in pairs]


def stable_proposal_id(scan_payload: Dict[str, Any], targets: List[Dict[str, Any]], action_type: str) -> str:
    idem = (scan_payload.get("idempotency") or {}).get("key") or ""
    payload = {
        "idempotency_key": idem,
        "action_type": action_type,
        "targets": targets,
    }
    return "proposal-" + sha256_hex(json.dumps(payload, sort_keys=True, separators=(",", ":")))


# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Build cleanup proposal from scan_payload + eii_result (folder target mode).")
    ap.add_argument("scan_payload_json", help="path to scan_payload.v1.json")
    ap.add_argument("eii_result_json", help="path to eii_result.json")
    ap.add_argument("out_cleanup_proposal_json", help="output path for cleanup_proposal.json")

    ap.add_argument("--min-group-gb", type=float, default=0.05,
                    help="minimum GB per extension group to include in notes (default: 0.05GB)")
    ap.add_argument("--default-folder", default="output",
                    help="default folder target path (relative to scan root) (default: output)")
    ap.add_argument("--force-output-target", action="store_true",
                    help="force a DIRECTORY target even if reclaimable is small / groups are tiny")

    args = ap.parse_args()

    scan_payload_path = Path(args.scan_payload_json).resolve()
    eii_path = Path(args.eii_result_json).resolve()
    out_path = Path(args.out_cleanup_proposal_json).resolve()

    scan_payload = read_json(scan_payload_path)
    eii = read_json(eii_path)

    # Policy / context
    policy = scan_payload.get("policy") or {}
    ctx = scan_payload.get("context") or {}
    data_level = policy.get("data_level") or "L1"

    # EII aggregates & optimization
    aggregates = eii.get("aggregates") or {}
    by_ext_gb = aggregates.get("by_extension_gb") or {}
    opt = eii.get("optimization_potential") or {}
    reclaimable_gb = to_num(opt.get("reclaimable_storage_gb"), 0.0)

    # Even if tiny, you may want to test the pipeline end-to-end
    estimated_reclaim_bytes = gb_to_bytes_decimal(reclaimable_gb)

    groups = pick_groups(by_ext_gb, min_group_gb=args.min_group_gb)

    # Targets (folder mode)
    folder = normalize_path(str(args.default_folder))
    targets: List[Dict[str, Any]] = []
    if folder:
        targets.append({"path": folder, "kind": "DIRECTORY"})

    actions: List[Dict[str, Any]] = []
    if targets and (args.force_output_target or estimated_reclaim_bytes > 0):
        actions.append(
            {
                "action_type": "cleanup.candidates.v1",
                "targets": targets,
                "estimated_reclaim_bytes": int(max(0, estimated_reclaim_bytes)),
                "notes": {
                    "adapter": "cleanup_adapter.v2.foldertargets",
                    "min_group_gb": float(args.min_group_gb),
                    "groups": groups[:50],
                },
            }
        )

    proposal_obj: Dict[str, Any] = {
        "schema_id": "aspectnova.cleanup_proposal",
        "schema_version": "aspectnova.cleanup_proposal.v1",
        "meta": {
            "generated_at": utc_now_z(),
            "proposal_id": "",  # filled below (stable)
            "engine": {
                "id": "cleanup_adapter",
                "version": "2.1.0",
            },
        },
        "context": {
            "org_id": ctx.get("org_id", ""),
            "workspace_id": ctx.get("workspace_id", ""),
            "device_id": ctx.get("device_id", ""),
        },
        "policy": {
            "data_level": data_level,
        },
        "source_scan": {
            "scan_id": (scan_payload.get("scan") or {}).get("scan_id", "scan-unknown"),
            "idempotency_key": (scan_payload.get("idempotency") or {}).get("key", ""),
        },
        "proposal": {
            "summary": {
                "actions_count": len(actions),
                "estimated_bytes_affected": int(max(0, estimated_reclaim_bytes)),
            },
            "actions": actions,
        },
    }

    proposal_obj["meta"]["proposal_id"] = stable_proposal_id(scan_payload, targets, "cleanup.candidates.v1")

    write_json(out_path, proposal_obj)
    print(f"[cleanup_adapter] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
