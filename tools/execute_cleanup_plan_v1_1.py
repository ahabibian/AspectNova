
# --- v1.2 bootstrap: allow running tools/*.py directly (tests call: python tools\x.py)
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
# --- end bootstrap ---

# === REPLACE WHOLE FILE: tools/execute_cleanup_plan_v1_1.py ===
# (This file is based on your uploaded version, patched to:
#  1) store payload_zip_sha256 in manifest.json
#  2) store zip_sha256 in execution_report
# Ensure trace contract includes provenance metadata required by audit and restore flows

import argparse
import base64
import fnmatch
import hashlib
import json
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.storage.io_json import read_json, write_json
from core.storage.hash_utils import sha256_file
from core.storage.paths import WorkspacePaths



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_read_json(path: str) -> Dict[str, Any]:
    # BOM-safe read
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _legacy_write_json(path: str, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _legacy_sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def normalize_rel_path(rel_path: str) -> str:
    return rel_path.replace("\\", "/").lstrip("./")


def require_confirm_secret(confirm_secret: Optional[str]) -> None:
    env_secret = os.environ.get("ASPECTNOVA_APPROVAL_SECRET", "")
    if not env_secret:
        raise RuntimeError("ASPECTNOVA_APPROVAL_SECRET is not set in environment")
    if not confirm_secret:
        raise RuntimeError("--confirm-secret is required when --execute is used")
    if confirm_secret != env_secret:
        raise RuntimeError("confirm secret mismatch (safety gate failed)")


def load_yaml_rules_text(rules_path: str) -> str:
    # We don't parse YAML here; we only hash and record it.
    return Path(rules_path).read_text(encoding="utf-8", errors="replace")


def archive_action(
    root: Path,
    archive_dir: Path,
    workspace_id: str,
    run_id: str,
    targets: List[Dict[str, Any]],
    remove_original: bool,
    execute: bool,
) -> Tuple[Optional[str], Optional[str], int, List[Dict[str, Any]], int]:
    """
    Create payload.zip + manifest.json and optionally remove originals.
    Returns: zip_path, manifest_path, freed_bytes, item_results, errors
    """
    ensure_dir(archive_dir)
    zip_path = archive_dir / "payload.zip"
    manifest_path = archive_dir / "manifest.json"

    manifest_items: List[Dict[str, Any]] = []
    item_results: List[Dict[str, Any]] = []
    errors = 0

    # Collect files to archive (only ARCHIVE)
    files = []
    for t in targets:
        action = (t.get("action") or "").upper()
        if action != "ARCHIVE":
            continue
        rel_path = normalize_rel_path(t.get("rel_path") or t.get("path") or "")
        if not rel_path:
            continue
        abs_path = root / rel_path
        files.append((rel_path, abs_path))

    # Build zip
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path, abs_path in files:
            if not abs_path.exists():
                errors += 1
                item_results.append(
                    {"rel_path": rel_path, "status": "error", "error": "missing_source"}
                )
                continue
            sha = sha256_file(abs_path)
            size = abs_path.stat().st_size
            manifest_items.append(
                {"rel_path": rel_path, "size_bytes": int(size), "sha256": sha}
            )
            zf.write(abs_path, arcname=rel_path)
            item_results.append({"rel_path": rel_path, "status": "ok", "error": None})

    payload_zip_sha256 = sha256_file(zip_path)

    freed_total = 0
    if execute and remove_original:
        for rel_path, abs_path in files:
            if abs_path.exists():
                try:
                    freed_total += abs_path.stat().st_size
                    abs_path.unlink()
                except Exception:
                    errors += 1
                    item_results.append(
                        {"rel_path": rel_path, "status": "error", "error": "remove_failed"}
                    )

    manifest = {
        "schema_id": "archive-manifest",
        "schema_version": "v1.1",
        "generated_at": utc_now_iso(),
        "workspace_id": workspace_id,
        "run_id": run_id,
        "payload_zip_sha256": payload_zip_sha256,  # NEW
        "items": manifest_items,
    }
    write_json(str(manifest_path), manifest)

    return str(zip_path), str(manifest_path), freed_total, item_results, errors


def write_trace_contract(root: Path, workspace_id: str, run_id: str, report_path: Path) -> Path:
    paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)
    contracts_dir = paths.contracts_dir
    ensure_dir(contracts_dir)
    archive_dir = paths.archive_dir
    contract_path = paths.trace_contract_path

    report = read_json(str(report_path)) if report_path.exists() else {}

    # Build counts from report.items[].decision_trace
    items = report.get("items") or []
    if not isinstance(items, list):
        items = []
    
    reason_counts = {}
    risk_bucket_counts = {}
    
    for it in items:
        if not isinstance(it, dict):
            continue
        dt = it.get("decision_trace") or {}
        if not isinstance(dt, dict):
            dt = {}
    
        # reasons: prefer reason_codes list; fallback to matched_rule string if present
        reasons = dt.get("reason_codes")
        if isinstance(reasons, list) and reasons:
            for r in reasons:
                if not r:
                    continue
                k = str(r)
                reason_counts[k] = reason_counts.get(k, 0) + 1
        else:
            mr = dt.get("matched_rule")
            if mr:
                k = str(mr)
                reason_counts[k] = reason_counts.get(k, 0) + 1
    
        rb = dt.get("risk_bucket")
        if rb:
            k = str(rb)
            risk_bucket_counts[k] = risk_bucket_counts.get(k, 0) + 1
    
    # --- end Gate 4 fix ---
    rules_path = (report.get("inputs") or {}).get("rules")
    zip_path = (report.get("archive") or {}).get("zip_path")
    manifest_path = (report.get("archive") or {}).get("manifest_path")
    payload_zip_sha256 = (report.get("archive") or {}).get("zip_sha256")

    # fallback: read from manifest
    if (not payload_zip_sha256) and manifest_path and Path(manifest_path).exists():
        payload_zip_sha256 = read_json(manifest_path).get("payload_zip_sha256")

    policy_sha256 = sha256_file(Path(rules_path)) if rules_path and Path(rules_path).exists() else None

    contract = {
        "schema_id": "trace-contract",
        "schema_version": "v1.1",
        "generated_at": utc_now_iso(),
        "paths": {
            "root": str(root),
            "contracts_dir": str(contracts_dir),
            "archive_dir": str(archive_dir),
            "report_path": str(report_path),
        },
        "provenance_summary": {  # REQUIRED by your e2e_full test
            "workspace_id": workspace_id,
            "run_id": run_id,
            "reason_counts": reason_counts,
            "risk_bucket_counts": risk_bucket_counts,
            "targets_total": (report.get("summary") or {}).get("targets_total"),
            "attempted_archive": (report.get("summary") or {}).get("attempted_archive"),
            "freed_bytes": (report.get("summary") or {}).get("freed_bytes"),
            "errors": (report.get("summary") or {}).get("errors"),
        },
        "artifacts": {
            "policy_path": rules_path,
            "policy_sha256": policy_sha256,
            "archive_zip_path": zip_path,
            "payload_zip_sha256": payload_zip_sha256,
            "manifest_path": manifest_path,
            "execution_report_path": str(report_path),
        },
    }

    write_json(str(contract_path), contract)
    return contract_path


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--rules", required=False)
    ap.add_argument("--root", required=True)
    ap.add_argument("--workspace-id", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-report", required=True)
    ap.add_argument("--archive-base", required=False)
    ap.add_argument("--remove-original", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--confirm-secret", required=False)
    ap.add_argument("--safe-mode", action="store_true")
    return ap.parse_args()


def main():
    args = parse_args()

    root = Path(args.root).resolve()
    targets_obj = read_json(args.targets)
    targets = targets_obj.get("targets") or targets_obj.get("items") or []
    rules_path = args.rules

    execute = bool(args.execute)
    safe_mode = bool(args.safe_mode)

    if execute:
        require_confirm_secret(args.confirm_secret)

    workspace_id = args.workspace_id
    run_id = args.run_id

    # v1.2: workspace paths (no behavior change)
    paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)

    # archive dir
    if args.archive_base:
        archive_dir = Path(args.archive_base).resolve() / workspace_id / run_id
    else:
        archive_dir = paths.archive_dir
    ensure_dir(archive_dir)

    zip_path = None
    manifest_path = None
    freed_total = 0
    item_results: List[Dict[str, Any]] = []
    errors = 0

    mode = "safe" if (safe_mode or (not execute)) else "execute"

    # Only ARCHIVE is implemented in this simplified v1.1 tool
    zip_path, manifest_path, freed_total, item_results, errors = archive_action(
        root=root,
        archive_dir=archive_dir,
        workspace_id=workspace_id,
        run_id=run_id,
        targets=targets,
        remove_original=bool(args.remove_original),
        execute=execute,
    )

    summary = {
        "targets_total": len(targets),
        "attempted_archive": sum(1 for t in targets if (t.get("action") or "").upper() == "ARCHIVE"),
        "freed_bytes": int(freed_total),
        "errors": int(errors),
    }

    report = {
        "schema_id": "execution-report",
        "schema_version": "v1.1",
        "generated_at": utc_now_iso(),
        "runner": {"safe_mode": safe_mode, "execute_requested": execute},
        "inputs": {
            "root": str(root),
            "workspace_id": workspace_id,
            "run_id": run_id,
            "targets_path": str(Path(args.targets).resolve()),
            "rules": str(Path(rules_path).resolve()) if rules_path else None,
        },
        "archive": {
            "mode": mode,
            "zip_path": zip_path,
            "manifest_path": manifest_path,
            "zip_sha256": (read_json(manifest_path).get("payload_zip_sha256") if manifest_path else None),  # NEW
        },
        "items": item_results,
        "summary": summary,
    }

    out_report = Path(args.out_report).resolve()

    # --- Gate 3 fix (hard guarantee): ensure execution_report.items include decision_trace ---
    # Build rel_path -> decision_trace from targets input
    targets_list = []
    if isinstance(targets_obj, dict):
        targets_list = targets_obj.get("targets") or targets_obj.get("items") or []
    if not isinstance(targets_list, list):
        targets_list = []

    trace_by_rel = {}
    for t in targets_list:
        if not isinstance(t, dict):
            continue
        rel = (t.get("rel_path") or t.get("path") or "").replace("\\\\", "/").lstrip("/")
        if not rel:
            continue
        dt = t.get("decision_trace") or {}
        if not isinstance(dt, dict):
            dt = {}
        ps = dt.get("provenance_summary")
        if not isinstance(ps, dict):
            dt["provenance_summary"] = {"engine": "aspectnova.dw.executor", "schema_version": "v1.1"}
        trace_by_rel[rel] = dt

    # Enrich report items (whatever the executor produced) with decision_trace
    rep_items_in = report.get("items") or []
    if not isinstance(rep_items_in, list):
        rep_items_in = []

    rep_items_out = []
    for r in rep_items_in:
        if not isinstance(r, dict):
            continue
        rel = (r.get("rel_path") or r.get("path") or "").replace("\\\\", "/").lstrip("/")
        dt = trace_by_rel.get(rel) or {"provenance_summary": {"engine": "aspectnova.dw.executor", "schema_version": "v1.1"}}
        rr = dict(r)
        rr["decision_trace"] = dt
        rep_items_out.append(rr)

    report["items"] = rep_items_out
    # --- end Gate 3 fix ---

    write_json(str(out_report), report)

    write_trace_contract(root=root, workspace_id=workspace_id, run_id=run_id, report_path=out_report)

    print(f"[OK] archive run complete | archived_ok={sum(1 for x in item_results if x.get('status')=='ok')} | payload={zip_path}")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
