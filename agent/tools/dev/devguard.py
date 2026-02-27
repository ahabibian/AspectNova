from __future__ import annotations

import argparse
import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _read_text_utf8_sig(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


def _read_bytes(p: Path) -> bytes:
    return p.read_bytes()


def _repo_root_from_this_file() -> Path:
    return Path(__file__).resolve().parents[2]


def _norm_rel(p: Path, root: Path) -> str:
    try:
        return str(p.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


@dataclass
class CheckResult:
    ok: bool
    details: Dict[str, Any]


def _paths_check(root: Path) -> CheckResult:
    required = [
        root / "dv.ps1",
        root / "tools" / "toolkit.ps1",
        root / "tools" / "ps_toolkit.ps1",
        root / "tools" / "dev" / "DV.Toolkit.ps1",
        root / "tools" / "dev" / "devguard.rules.json",
        root / "tools" / "dev" / "devguard.py",
    ]
    missing = [str(p) for p in required if not p.exists()]
    return CheckResult(ok=(len(missing) == 0), details={"missing": missing})


def _no_bom_check(root: Path) -> CheckResult:
    globs_ = [
        str(root / "*.ps1"),
        str(root / "tools" / "**" / "*.ps1"),
        str(root / "tools" / "**" / "*.py"),
        str(root / "tools" / "**" / "*.json"),
        str(root / "tools" / "**" / "*.yaml"),
        str(root / "tools" / "**" / "*.yml"),
        str(root / "docs" / "**" / "*.md"),
        str(root / "*.md"),
    ]
    files: List[Path] = []
    for g in globs_:
        for f in glob.glob(g, recursive=True):
            fp = Path(f)
            if fp.is_file():
                files.append(fp)

    bom = b"\xef\xbb\xbf"
    bad: List[str] = []
    for p in sorted(set(files), key=lambda x: str(x).lower()):
        try:
            b = _read_bytes(p)
            if b.startswith(bom):
                bad.append(_norm_rel(p, root))
        except Exception:
            bad.append(_norm_rel(p, root))

    return CheckResult(ok=(len(bad) == 0), details={"bom_files": bad})


def _stages_check(root: Path) -> CheckResult:
    rules_path = root / "tools" / "dev" / "devguard.rules.json"
    if not rules_path.exists():
        return CheckResult(ok=False, details={"error": f"missing rules file: {str(rules_path)}"})

    try:
        _ = json.loads(_read_text_utf8_sig(rules_path))
        return CheckResult(ok=True, details={"rules_ok": True})
    except Exception as e:
        return CheckResult(ok=False, details={"error": f"invalid rules json: {e!r}"})


def _compile_patterns(patterns: List[str]) -> List[Tuple[str, re.Pattern]]:
    compiled: List[Tuple[str, re.Pattern]] = []
    for pat in patterns:
        compiled.append((pat, re.compile(pat, flags=re.IGNORECASE | re.MULTILINE)))
    return compiled


def _match_any_exception(rel: str, exceptions: List[str]) -> bool:
    for ex in exceptions:
        exn = ex.replace("\\", "/")
        if "*" in exn or "?" in exn or "[" in exn:
            if glob.fnmatch.fnmatch(rel, exn):
                return True
        else:
            if rel == exn:
                return True
    return False


def _forbidden_ps_patterns_check(root: Path, rules: Dict[str, Any]) -> CheckResult:
    forbidden = rules.get("forbidden_ps_patterns", [])
    scan_globs = rules.get("scan_globs", [])
    exceptions = rules.get("exceptions", [])

    if not isinstance(forbidden, list) or not isinstance(scan_globs, list) or not isinstance(exceptions, list):
        return CheckResult(
            ok=False,
            details={"error": "rules schema invalid: expected lists for forbidden_ps_patterns/scan_globs/exceptions"},
        )

    compiled = _compile_patterns([str(x) for x in forbidden])

    hits: List[Dict[str, Any]] = []
    files: List[Path] = []
    for g in scan_globs:
        gpath = str((root / g).resolve()) if not os.path.isabs(g) else g
        for f in glob.glob(gpath, recursive=True):
            fp = Path(f)
            if fp.is_file():
                files.append(fp)

    for p in sorted(set(files), key=lambda x: str(x).lower()):
        rel = _norm_rel(p, root)
        if _match_any_exception(rel, [str(x) for x in exceptions]):
            continue

        try:
            text = _read_text_utf8_sig(p)
        except Exception as e:
            hits.append({"file": rel, "pattern": "<unreadable>", "error": repr(e)})
            continue

        for raw_pat, rx in compiled:
            m = rx.search(text)
            if m:
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                snippet = text[start:end].replace("\r", "\\r").replace("\n", "\\n")
                hits.append({"file": rel, "pattern": raw_pat, "snippet": snippet})

    return CheckResult(ok=(len(hits) == 0), details={"hits": hits, "scan_count": len(set(files))})


def _print_report(results: Dict[str, CheckResult]) -> None:
    def line(name: str, r: CheckResult) -> str:
        return f"{name}: {'OK' if r.ok else 'FAIL'}"

    print("DEVGUARD")
    for key in ["no_bom", "paths", "stages", "forbidden_ps_patterns"]:
        if key in results:
            print(" - " + line(key, results[key]))

    rfp = results.get("forbidden_ps_patterns")
    if rfp and not rfp.ok:
        hits = rfp.details.get("hits", [])
        if hits:
            print("   hits:")
            for h in hits:
                f = h.get("file", "?")
                pat = h.get("pattern", "?")
                sn = h.get("snippet", "")
                print(f"    - {f} :: {pat} :: {sn}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="devguard")
    ap.add_argument("--root", default=None, help="Repo root override")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else _repo_root_from_this_file()
    os.environ["DV_ROOT"] = str(root)

    rules_path = root / "tools" / "dev" / "devguard.rules.json"
    try:
        rules = json.loads(_read_text_utf8_sig(rules_path)) if rules_path.exists() else {}
    except Exception as e:
        rules = {"_load_error": repr(e)}

    results: Dict[str, CheckResult] = {}
    results["no_bom"] = _no_bom_check(root)
    results["paths"] = _paths_check(root)
    results["stages"] = _stages_check(root)
    results["forbidden_ps_patterns"] = _forbidden_ps_patterns_check(root, rules)

    _print_report(results)

    overall_ok = all(r.ok for r in results.values())
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())