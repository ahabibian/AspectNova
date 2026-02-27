import json
import sys
from pathlib import Path
from collections import Counter

def load_json(path: Path):
    # tolerate UTF-8 BOM
    return json.loads(path.read_text(encoding="utf-8-sig"))

def fail(payload: dict, code: int = 1):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(code)

def main():
    if len(sys.argv) != 3:
        print("USAGE: python tools/gate_evidence_pack.py <evidence_pack.json> <policy.json>")
        raise SystemExit(2)

    pack_path = Path(sys.argv[1])
    policy_path = Path(sys.argv[2])

    pack = load_json(pack_path)
    policy = load_json(policy_path)

    req = policy.get("requirements") or {}
    reasons = []

    # --- key checks
    must_have_keys = req.get("must_have_keys") or []
    missing_keys = [k for k in must_have_keys if k not in pack]
    if missing_keys:
        reasons.append({"type": "missing_keys", "detail": missing_keys})

    nodes = pack.get("nodes") or []
    edges = pack.get("edges") or []
    indexes = pack.get("indexes") or {}

    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(indexes, dict):
        reasons.append({"type": "invalid_types", "detail": "nodes/edges/indexes type mismatch"})

    # --- index checks
    must_have_indexes = req.get("must_have_indexes") or []
    missing_indexes = [k for k in must_have_indexes if k not in indexes]
    if missing_indexes:
        reasons.append({"type": "missing_indexes", "detail": missing_indexes})

    by_path_norm = indexes.get("by_path_norm") or {}
    if "by_path_norm" in must_have_indexes and (not isinstance(by_path_norm, dict) or len(by_path_norm) == 0):
        reasons.append({"type": "empty_by_path_norm", "detail": len(by_path_norm) if isinstance(by_path_norm, dict) else None})

    # --- counts (FIXED: edges are not nodes)
    c_node_type = Counter(n.get("type") for n in nodes)
    min_counts = req.get("min_counts") or {}

    for k, v in min_counts.items():
        v = int(v)
        if k == "edge":
            got = len(edges) if isinstance(edges, list) else 0
            if got < v:
                reasons.append({"type": "min_count_fail", "detail": {"type": "edge", "min": v, "got": got}})
        else:
            got = c_node_type.get(k, 0)
            if got < v:
                reasons.append({"type": "min_count_fail", "detail": {"type": k, "min": v, "got": got}})

    # --- subtype minimums
    c_sub = Counter(f"{n.get('type')}:{n.get('subtype')}" for n in nodes)
    expect_node_subtypes_min = req.get("expect_node_subtypes_min") or {}
    for k, v in expect_node_subtypes_min.items():
        v = int(v)
        if c_sub.get(k, 0) < v:
            reasons.append({"type": "subtype_min_fail", "detail": {"subtype": k, "min": v, "got": c_sub.get(k, 0)}})

    # --- sources presence
    expect_sources = req.get("expect_sources") or {}
    for k, v in expect_sources.items():
        v = int(v)
        if c_sub.get(k, 0) < v:
            reasons.append({"type": "source_missing", "detail": {"source": k, "min": v, "got": c_sub.get(k, 0)}})

    # --- tolerance: by_path_norm size == asset_count
    tol = req.get("tolerances") or {}
    if tol.get("by_path_norm_equals_asset_count") is True:
        asset_count = indexes.get("asset_count")
        if isinstance(asset_count, int) and isinstance(by_path_norm, dict):
            if len(by_path_norm) != asset_count:
                reasons.append({"type": "by_path_norm_size_mismatch", "detail": {"by_path_norm": len(by_path_norm), "asset_count": asset_count}})

    status = "PASS" if len(reasons) == 0 else "FAIL"

    out = {
        "stage": policy.get("stage", "evidence_pack"),
        "policy_version": policy.get("policy_version", "unknown"),
        "status": status,
        "reasons": reasons,
        "inputs": {"pack": str(pack_path), "policy": str(policy_path)},
        "counts": {
            "nodes": len(nodes) if isinstance(nodes, list) else None,
            "edges": len(edges) if isinstance(edges, list) else None,
            "by_path_norm": len(by_path_norm) if isinstance(by_path_norm, dict) else None
        },
        "node_type_top": dict(c_node_type.most_common(10)),
        "node_subtype_top": dict(c_sub.most_common(10))
    }

    if status == "PASS":
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    fail(out, 1)

if __name__ == "__main__":
    main()

