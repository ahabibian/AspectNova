import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import win32security

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def normalize_path(p: str) -> str:
    return p.strip().lower()

def _sid_to_str(sid) -> str:
    return win32security.ConvertSidToStringSid(sid)

def _sid_to_account(sid):
    try:
        name, domain, _ = win32security.LookupAccountSid(None, sid)
        return domain, name
    except Exception:
        return None, None

def _make_edge(edge_type: str, from_id: str, to_id: str, props: dict | None = None):
    eid = f"edge:{edge_type}:{sha1(from_id + '->' + to_id)}"
    e = {"id": eid, "type": edge_type, "from": from_id, "to": to_id}
    if props:
        e["properties"] = props
    return e

def _asset_hash(asset_id: str) -> str:
    # asset:file:<sha1>
    return asset_id.split(":")[-1]

def enrich(evidence_pack_path: Path, scan_canonical_v1_path: Path, out_path: Path, run_id: str):
    pack = json.loads(evidence_pack_path.read_text(encoding="utf-8"))
    scan = json.loads(scan_canonical_v1_path.read_text(encoding="utf-8"))

    items = scan.get("items") or scan.get("files") or []
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("scan v1 has no items/files array")

    nodes = pack.get("nodes") or []
    edges = pack.get("edges") or []
    pack["nodes"] = nodes
    pack["edges"] = edges

    node_ids = set(n.get("id") for n in nodes if n.get("id"))
    edge_ids = set(e.get("id") for e in edges if e.get("id"))

    indexes = pack.get("indexes") or {}
    by_path_norm = indexes.get("by_path_norm") or {}
    if not isinstance(by_path_norm, dict) or len(by_path_norm) == 0:
        raise ValueError("evidence_pack has no indexes.by_path_norm; rebuild evidence pack first")

    observed_at = datetime.now(timezone.utc).isoformat()

    source_id = f"src:win:sd:{run_id}"
    if source_id not in node_ids:
        nodes.append({
            "id": source_id,
            "type": "source",
            "subtype": "windows_security_descriptor",
            "properties": {
                "collector": "owner_enricher",
                "api": "GetFileSecurity/OWNER_SECURITY_INFORMATION",
                "run_id": run_id
            },
            "quality": {"reliability_score": 0.8}
        })
        node_ids.add(source_id)

    ok = 0
    fail = 0
    skipped_no_asset = 0
    added_obs = 0
    added_claims = 0

    not_found = 0
    access_denied = 0
    other_error = 0

    # classify pywin32 errors reliably
    try:
        import pywintypes  # type: ignore
    except Exception:
        pywintypes = None

    for it in items:
        path_rel = it.get("path_rel") or it.get("path")
        path_abs = it.get("path_abs") or it.get("path")

        if not path_rel or not path_abs:
            continue

        path_norm = normalize_path(path_rel)
        asset_id = by_path_norm.get(path_norm)

        if not asset_id or asset_id not in node_ids:
            skipped_no_asset += 1
            continue

        asset_hash = _asset_hash(asset_id)

        obs_id = f"obs:win:owner:{sha1(asset_id + run_id)}"
        claim_id = f"claim:file.owner:{asset_hash}"

        # defaults for this item
        owner_ok = False
        sid_str = None
        owner_value = None
        error_code = None
        error_detail = None

        try:
            if not Path(path_abs).exists():
                raise FileNotFoundError(path_abs)

            sd = win32security.GetFileSecurity(path_abs, win32security.OWNER_SECURITY_INFORMATION)
            sid = sd.GetSecurityDescriptorOwner()
            sid_str = _sid_to_str(sid)
            domain, name = _sid_to_account(sid)

            owner_value = (f"{domain}\\{name}" if domain else name) if name else sid_str

            ok += 1
            owner_ok = True

        except Exception as e:
            fail += 1
            owner_ok = False
            sid_str = None
            owner_value = None

            error_detail = str(e)
            error_code = "other"

            # classify
            try:
                if isinstance(e, FileNotFoundError):
                    error_code = "not_found"
                    not_found += 1
                elif pywintypes is not None and isinstance(e, pywintypes.error):
                    we = getattr(e, "winerror", None)
                    if we in (2, 3):
                        error_code = "not_found"
                        not_found += 1
                    elif we == 5:
                        error_code = "access_denied"
                        access_denied += 1
                    else:
                        error_code = f"winerror_{we}" if we is not None else "winerror"
                        other_error += 1
                else:
                    other_error += 1
            except Exception:
                other_error += 1

        # add observation node once
        if obs_id not in node_ids:
            nodes.append({
                "id": obs_id,
                "type": "observation",
                "subtype": "win_sd_owner_lookup",
                "properties": {
                    "path_rel": path_rel,
                    "path_abs": path_abs,
                    "path_norm": path_norm,
                    "ok": owner_ok,
                    "owner": owner_value,
                    "owner_sid": sid_str,
                    "error_code": (error_code if not owner_ok else None),
                    "error_detail": (error_detail if not owner_ok else None),
                },
                "provenance": {
                    "source_id": source_id,
                    "observed_at_utc": observed_at,
                    "collector": "owner_enricher"
                },
                "quality": {"reliability_score": 0.8}
            })
            node_ids.add(obs_id)
            added_obs += 1

        # edges: obs -> asset, obs -> source
        e1 = _make_edge("about", obs_id, asset_id)
        if e1["id"] not in edge_ids:
            edges.append(e1); edge_ids.add(e1["id"])

        e2 = _make_edge("observed_by", obs_id, source_id)
        if e2["id"] not in edge_ids:
            edges.append(e2); edge_ids.add(e2["id"])

        # claim only if ok
        if owner_ok and owner_value:
            if claim_id not in node_ids:
                nodes.append({
                    "id": claim_id,
                    "type": "claim",
                    "subtype": "file_owner",
                    "properties": {"predicate": "file.owner", "value": owner_value},
                    "provenance": {
                        "created_at_utc": observed_at,
                        "method": "derived_from_observation",
                        "source_id": source_id
                    },
                    "quality": {"confidence": 0.85}
                })
                node_ids.add(claim_id)
                added_claims += 1

            e3 = _make_edge("supports", obs_id, claim_id)
            if e3["id"] not in edge_ids:
                edges.append(e3); edge_ids.add(e3["id"])

            e4 = _make_edge("about", claim_id, asset_id)
            if e4["id"] not in edge_ids:
                edges.append(e4); edge_ids.add(e4["id"])

    out_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "run_id": run_id,
        "generated_at_utc": observed_at,
        "input_pack": str(evidence_pack_path),
        "scan_v1": str(scan_canonical_v1_path),
        "output_pack": str(out_path),
        "owner_lookup": {
            "ok": ok,
            "fail": fail,
            "not_found": not_found,
            "access_denied": access_denied,
            "other_error": other_error,
            "skipped_no_asset": skipped_no_asset
        },
        "added": {"observations": added_obs, "claims": added_claims},
        "counts": {"node_count": len(nodes), "edge_count": len(edges)}
    }
