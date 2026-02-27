import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def normalize_path(p: str) -> str:
    return p.strip().lower()

def build(scan_canonical_path: Path, run_id: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    scan = json.loads(scan_canonical_path.read_text(encoding="utf-8"))
    items = scan.get("items") or scan.get("files") or []
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("scan canonical has no items/files array")

    generated_at = datetime.now(timezone.utc).isoformat()

    pack = {
        "contract_version": "evidence_pack/1.1",
        "schema_version": "1.1.0",
        "pack_id": f"pack:{run_id}",
        "generated_at_utc": generated_at,
        "generator": {"name": "evidence_builder", "version": "1.1.0", "run_id": run_id},
        "nodes": [],
        "edges": [],
        "indexes": {}
    }

    nodes = pack["nodes"]
    edges = pack["edges"]

    src_id = f"src:scan:{run_id}"
    nodes.append({
        "id": src_id,
        "type": "source",
        "subtype": "filesystem_scan",
        "properties": {"run_id": run_id, "input": str(scan_canonical_path)},
        "quality": {"reliability_score": 0.7}
    })

    node_ids = {src_id}
    edge_ids = set()
    by_path_norm = {}

    asset_count = 0
    observation_count = 0
    claim_count = 0

    def add_edge(edge_type: str, a: str, b: str):
        eid = f"edge:{edge_type}:{sha1(a + '->' + b)}"
        if eid in edge_ids:
            return
        edges.append({"id": eid, "type": edge_type, "from": a, "to": b})
        edge_ids.add(eid)

    for it in items:
        path_rel = it.get("path_rel") or it.get("path")
        if not path_rel:
            continue

        size_bytes = it.get("size_bytes")
        if size_bytes is None:
            size_bytes = it.get("size")

        mtime_raw = it.get("mtime_raw")
        if mtime_raw is None:
            mtime_raw = it.get("mtime")

        path_norm = normalize_path(path_rel)
        asset_hash = sha1(path_norm)
        asset_id = f"asset:file:{asset_hash}"

        if asset_id not in node_ids:
            nodes.append({
                "id": asset_id,
                "type": "asset",
                "subtype": "file",
                "properties": {"path_rel": path_rel, "path_norm": path_norm},
                "quality": {"reliability_score": 0.7}
            })
            node_ids.add(asset_id)
            asset_count += 1

        by_path_norm[path_norm] = asset_id

        obs_id = f"obs:scan:meta:{sha1(asset_id + run_id)}"
        if obs_id not in node_ids:
            nodes.append({
                "id": obs_id,
                "type": "observation",
                "subtype": "scan_file_meta",
                "properties": {
                    "path_rel": path_rel,
                    "path_norm": path_norm,
                    "size_bytes": size_bytes,
                    "mtime_raw": mtime_raw
                },
                "provenance": {"source_id": src_id, "observed_at_utc": generated_at, "collector": "evidence_builder"},
                "quality": {"reliability_score": 0.7}
            })
            node_ids.add(obs_id)
            observation_count += 1

        add_edge("about", obs_id, asset_id)
        add_edge("observed_by", obs_id, src_id)

        claim_id = f"claim:file.path_norm:{asset_hash}"
        if claim_id not in node_ids:
            nodes.append({
                "id": claim_id,
                "type": "claim",
                "subtype": "file_path_norm",
                "properties": {"predicate": "file.path_norm", "value": path_norm},
                "provenance": {"created_at_utc": generated_at, "method": "scan_projection", "source_id": src_id},
                "quality": {"confidence": 0.9}
            })
            node_ids.add(claim_id)
            claim_count += 1

        add_edge("supports", obs_id, claim_id)

    pack["indexes"] = {
        "asset_count": asset_count,
        "observation_count": observation_count,
        "claim_count": claim_count,
        "by_path_norm": by_path_norm
    }

    (out_dir / "evidence_pack.v1.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "evidence_pack.stats.json").write_text(json.dumps({
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "counts": {"asset_count": asset_count, "observation_count": observation_count, "claim_count": claim_count}
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"asset_count": asset_count, "observation_count": observation_count, "claim_count": claim_count}
