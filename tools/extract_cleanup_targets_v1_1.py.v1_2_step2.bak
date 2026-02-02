from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Dict[str, Any]:
    # BOM-safe read
    txt = Path(path).read_text(encoding="utf-8-sig")
    return json.loads(txt)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def glob_to_regex_with_globstar(pat: str) -> str:
    pat = (pat or "").replace("\\", "/").lstrip("/")
    out = []
    i = 0
    n = len(pat)
    while i < n:
        c = pat[i]
        if c == "*":
            if (i + 1 < n) and pat[i + 1] == "*":
                i += 2
                if (i < n) and pat[i] == "/":
                    i += 1
                    out.append(r"(?:[^/]+/)*")
                else:
                    out.append(r".*")
                continue
            out.append(r"[^/]*")
            i += 1
            continue
        if c == "?":
            out.append(r"[^/]")
            i += 1
            continue
        if c in ".^$+{}[]()|\\":
            out.append("\\" + c)
            i += 1
            continue
        out.append(c)
        i += 1
    return r"^" + "".join(out) + r"$"


def match_one(rel_path: str, pattern: str) -> bool:
    rel_path = (rel_path or "").replace("\\", "/").lstrip("/")
    pattern = (pattern or "").replace("\\", "/").lstrip("/")
    rx = glob_to_regex_with_globstar(pattern)
    return re.fullmatch(rx, rel_path) is not None


def match_any(rel_path: str, patterns: List[str]) -> bool:
    for p in patterns:
        if isinstance(p, str) and p.strip():
            if match_one(rel_path, p.strip()):
                return True
    return False


@dataclass
class GlobalCfg:
    matcher: str = "globstar-regex"


@dataclass
class Rule:
    rule_id: str
    action: str
    priority: int = 0
    path_globs: List[str] = None
    risk_bucket: Optional[str] = None

    def __post_init__(self):
        if self.path_globs is None:
            self.path_globs = []


def collect_globs(rule_obj: Dict[str, Any]) -> List[str]:
    keys = ["path_globs", "path_glob", "globs", "glob", "patterns", "includes", "include"]
    globs: List[str] = []
    m = rule_obj.get("match")
    m = m if isinstance(m, dict) else {}
    for k in keys:
        for v in as_list(rule_obj.get(k)):
            if isinstance(v, str) and v.strip():
                globs.append(v.strip())
        for v in as_list(m.get(k)):
            if isinstance(v, str) and v.strip():
                globs.append(v.strip())
    return [g.replace("\\", "/").lstrip("/") for g in globs]


def extract_action(rule_obj: Dict[str, Any]) -> str:
    then = rule_obj.get("then")
    then = then if isinstance(then, dict) else {}
    act = rule_obj.get("action") or then.get("action") or "NOOP"
    return str(act).strip().upper()


def extract_risk_bucket(rule_obj: Dict[str, Any], action: str) -> str:
    then = rule_obj.get("then")
    then = then if isinstance(then, dict) else {}
    rb = rule_obj.get("risk_bucket") or then.get("risk_bucket")
    if rb:
        return str(rb).strip().upper()
    if action == "DELETE":
        return "A"
    if action in ("MOVE", "ARCHIVE"):
        return "B"
    return "C"


def load_policy(policy_path: Path) -> Tuple[GlobalCfg, List[Rule]]:
    d = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    d = d if isinstance(d, dict) else {}
    cfg = GlobalCfg()

    rules_raw = d.get("rules") or []
    if not isinstance(rules_raw, list):
        rules_raw = []

    rules: List[Rule] = []
    for r in rules_raw:
        if not isinstance(r, dict):
            continue
        rid = r.get("id") or r.get("name") or r.get("rule_id") or "unknown.rule"
        action = extract_action(r)
        priority = int(r.get("priority") or 0)
        globs = collect_globs(r)
        rb = extract_risk_bucket(r, action)
        rules.append(Rule(rule_id=str(rid), action=action, priority=priority, path_globs=globs, risk_bucket=rb))

    rules.sort(key=lambda rr: rr.priority, reverse=True)
    return cfg, rules


def choose_rule(rel_path: str, rules: List[Rule]) -> Optional[Rule]:
    for r in rules:
        if match_any(rel_path, r.path_globs):
            return r
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", required=True)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    scan_path = Path(args.scan).resolve()
    policy_path = Path(args.rules).resolve()
    out_path = Path(args.out).resolve()

    cfg, rules = load_policy(policy_path)
    scan_obj = read_json(scan_path)

    items = scan_obj.get("items") or scan_obj.get("files") or []
    if not isinstance(items, list):
        raise SystemExit("scan_result.items.json: 'items' is not a list")

    targets: List[Dict[str, Any]] = []
    by_action = {"DELETE": 0, "ARCHIVE": 0, "MOVE": 0, "NOOP": 0}

    for it in items:
        if not isinstance(it, dict):
            continue
        rel = (it.get("rel_path") or it.get("path") or "").replace("\\", "/").lstrip("/")
        if not rel:
            continue

        size = int(it.get("size_bytes") or it.get("size") or 0)
        ext = Path(rel).suffix.lower()

        rule = choose_rule(rel, rules)
        matched_rule = rule.rule_id if rule else None
        action = rule.action if rule else "NOOP"
        rb = rule.risk_bucket if rule else "C"

        dtrace = {
            "matcher": cfg.matcher,
            "matched_rule": matched_rule,
            "reason_codes": [matched_rule] if matched_rule else [],
            "risk_bucket": rb,
            "provenance_summary": {
                "engine": "aspectnova.dw.extractor",
                "schema_version": "v1.1",
                "inputs": {
                    "scan_path": str(scan_path),
                    "policy_path": str(policy_path),
                },
                "evidence": {
                    "rule_id": matched_rule,
                    "action": action,
                    "ext": ext,
                    "size_bytes": size,
                },
            },
        }

        obj = {
            "action": action,
            "rel_path": rel,
            "path": rel,
            "matched_rule": matched_rule,
            "ext": ext,
            "size_bytes": size,
            "decision_trace": dtrace,
        }
        targets.append(obj)
        by_action[action] = by_action.get(action, 0) + 1

    out_obj = {
        "schema_id": "cleanup-targets",
        "schema_version": "v1.1",
        "generated_at": utc_now_iso(),
        "root": str(root),
        "inputs": {"scan_path": str(scan_path), "policy_path": str(policy_path)},
        "summary": {"targets_total": len(targets), "by_action": by_action, "matcher": cfg.matcher},
        "targets": targets,
        "items": targets,  # compatibility alias for tests
    }

    write_json(out_path, out_obj)
    print(f"[OK] wrote {out_path} | targets={len(targets)} | by_action={by_action} | glob=globstar-regex")


if __name__ == "__main__":
    main()
