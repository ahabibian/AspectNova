from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml


# -----------------------------
# Data model
# -----------------------------

@dataclass
class Rule:
    id: str
    action: str
    category: str
    priority: int
    path_globs: List[str]
    rationale: str = ""


def _norm_path(p: str) -> str:
    return (p or "").replace("\\", "/").lstrip("./")


def _as_list(x) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def load_rules(path: Path) -> Tuple[Dict[str, Any], List[Rule]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    global_cfg = data.get("global") or {}
    rules_raw = data.get("rules") or []

    rules: List[Rule] = []
    for r in rules_raw:
        if not isinstance(r, dict):
            continue
        rules.append(
            Rule(
                id=str(r.get("id") or "").strip(),
                action=str(r.get("action") or "").strip().upper(),
                category=str(r.get("category") or "").strip(),
                priority=int(r.get("priority") or 0),
                path_globs=[str(x) for x in _as_list(r.get("path_globs"))],
                rationale=str(r.get("rationale") or "").strip(),
            )
        )

    # highest priority first
    rules.sort(key=lambda rr: rr.priority, reverse=True)
    return global_cfg, rules


def _match_any_glob(path_posix: str, globs: List[str]) -> bool:
    # NOTE: this uses Path.match semantics (not fnmatch), but kept compatible:
    # - Some deployments swap matcher. Keep conservative.
    p = Path(path_posix)
    for g in globs:
        g = _norm_path(g)
        if not g:
            continue
        try:
            if p.match(g):
                return True
        except Exception:
            # fallback to fnmatch
            if fnmatch.fnmatch(path_posix, g):
                return True
    return False


def choose_rule(path_posix: str, rules: List[Rule]) -> Optional[Rule]:
    for r in rules:
        if _match_any_glob(path_posix, r.path_globs):
            return r
    return None


def _load_scan_items(scan_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(scan_path.read_text(encoding="utf-8"))
    items = data.get("items") or data.get("files") or []
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in items:
        if isinstance(it, dict):
            out.append(it)
    return out


def _stat_payload(root: Path, rel_posix: str, kind_hint: Optional[str] = None) -> Dict[str, Any]:
    p = root / rel_posix
    exists = p.exists()
    kind = kind_hint
    if kind is None:
        if exists and p.is_dir():
            kind = "dir"
        else:
            kind = "file"
    size = None
    if exists and kind == "file":
        try:
            size = p.stat().st_size
        except Exception:
            size = None

    mtime_utc = None
    if exists:
        try:
            mtime_utc = p.stat().st_mtime
        except Exception:
            mtime_utc = None

    return {
        "size_bytes": size if size is not None else 0,
        "kind": kind,
        "exists": exists,
        "last_modified_utc": None,  # filled by scan item if present
    }


def _derive_dirs(targets: List[Dict[str, Any]], depth: int = 6) -> List[Dict[str, Any]]:
    # Create directory targets for parents (helpful for later "empty dir delete" executor).
    seen = set()
    dirs = []
    for t in targets:
        rp = _norm_path(t.get("path") or "")
        if not rp:
            continue
        parts = rp.split("/")
        # only derive if the target is nested enough
        for i in range(1, min(len(parts), depth + 1)):
            d = "/".join(parts[:i])
            if d and d not in seen:
                seen.add(d)
                dirs.append({"path": d, "kind": "dir"})
    return dirs


def build_targets(
    scan_path: Path,
    rules_path: Path,
    out_path: Path,
    root: Path,
    derive_depth: int = 0,
) -> Dict[str, Any]:
    global_cfg, rules = load_rules(rules_path)
    items = _load_scan_items(scan_path)

    targets: List[Dict[str, Any]] = []
    protected_hits = 0

    # Apply to scan items
    for it in items:
        rel = _norm_path(str(it.get("path") or ""))
        if not rel:
            continue

        kind_hint = it.get("kind")
        r = choose_rule(rel, rules)

        if r is None:
            # default NOOP if no rule at all
            action = "NOOP"
            category = "protected"
            rid = "default.noop"
            rationale = "Default: no matching rule."
        else:
            action = r.action
            category = r.category
            rid = r.id
            rationale = r.rationale or ""

        if category == "protected":
            protected_hits += 1

        stats = _stat_payload(root, rel, kind_hint=kind_hint)
        # prefer scan timestamps if present
        if it.get("last_modified_utc"):
            stats["last_modified_utc"] = it.get("last_modified_utc")

        # estimated savings only when delete/archive/move (placeholder)
        est_save = stats.get("size_bytes") or 0
        if action == "NOOP":
            est_save = 0

        targets.append(
            {
                "path": rel,
                "category": category,
                "action": action,
                "confidence": float(it.get("confidence") or 0.0),
                "matched_rule": rid,
                "rationale": rationale,
                "stats": stats,
                "tags": it.get("tags") or [],
                "estimated_savings_bytes": int(est_save),
            }
        )

    # Optionally derive directory entries
    if derive_depth and derive_depth > 0:
        derived_dirs = _derive_dirs(targets, depth=derive_depth)
        for d in derived_dirs:
            rel = _norm_path(d["path"])
            r = choose_rule(rel, rules)
            if r is None:
                action = "NOOP"
                category = "protected"
                rid = "default.noop"
                rationale = "Default: no matching rule."
            else:
                action = r.action
                category = r.category
                rid = r.id
                rationale = r.rationale or ""

            stats = _stat_payload(root, rel, kind_hint="dir")
            if action == "NOOP":
                est_save = 0
            else:
                est_save = 0  # dirs savings counted via contained files elsewhere

            targets.append(
                {
                    "path": rel,
                    "category": category,
                    "action": action,
                    "confidence": 0.0,
                    "matched_rule": rid,
                    "rationale": rationale,
                    "stats": stats,
                    "tags": [],
                    "estimated_savings_bytes": int(est_save),
                }
            )

    # Summaries
    by_action = {"DELETE": 0, "ARCHIVE": 0, "MOVE": 0, "NOOP": 0}
    total_save = 0
    for t in targets:
        a = (t.get("action") or "NOOP").upper()
        by_action[a] = by_action.get(a, 0) + 1
        total_save += int(t.get("estimated_savings_bytes") or 0)

    report = {
        "schema_version": "cleanup_targets_v1",
        "ruleset": str(rules_path).replace("\\", "/"),
        "scan_input": str(scan_path).replace("\\", "/"),
        "summary": {
            "targets_total": len(targets),
            "by_action": by_action,
            "protected_hits": protected_hits,
            "estimated_savings_bytes_total": total_save,
        },
        "targets": targets,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True, help="Path to scan_result.items.json")
    ap.add_argument("--rules", required=True, help="Path to cleanup_rules yaml")
    ap.add_argument("--out", required=True, help="Output json path")
    ap.add_argument("--root", default=".", help="Repo root (for filesystem stats)")
    ap.add_argument("--derive-dirs-depth", type=int, default=0, help="Derive directory targets up to depth")
    args = ap.parse_args()

    report = build_targets(
        scan_path=Path(args.scan),
        rules_path=Path(args.rules),
        out_path=Path(args.out),
        root=Path(args.root),
        derive_depth=int(args.derive_dirs_depth or 0),
    )
    print(f"[OK] wrote {args.out} | targets={report['summary']['targets_total']}")


if __name__ == "__main__":
    main()
