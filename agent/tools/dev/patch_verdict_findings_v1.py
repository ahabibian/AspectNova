from __future__ import annotations
from pathlib import Path
import re

rp = Path("run_verdict_stage.py")
if not rp.exists():
    raise SystemExit("PATCH FAIL: run_verdict_stage.py not found in repo root.")

txt = rp.read_text(encoding="utf-8")

marker = "VERDICT_FINDINGS_RULES_V1"
if marker in txt:
    print("PATCH SKIP: already applied")
    raise SystemExit(0)

# We inject rules right BEFORE verdict.json is written.
# Try a few common patterns.
patterns = [
    r'(?m)^(?P<indent>\s*)out_path\.write_text\(',
    r'(?m)^(?P<indent>\s*)verdict_path\.write_text\(',
    r'(?m)^(?P<indent>\s*)Path\([rR]?[\'"]verdict\.json[\'"]\)\.write_text\(',
]

m = None
for pat in patterns:
    m = re.search(pat, txt)
    if m:
        break

if not m:
    # last resort: find any mention of verdict.json and inject near it
    m2 = re.search(r'(?m)^(?P<indent>\s*).*(verdict\.json).*$', txt)
    if not m2:
        raise SystemExit("PATCH FAIL: could not locate where verdict.json is written.")
    m = m2

indent = m.group("indent")

inject = f"""
{indent}# --- {marker}
{indent}# Minimal, deterministic findings rules (enterprise-friendly baseline)
{indent}try:
{indent}    # canonical scan is the most stable input for rules
{indent}    canon_p = Path("runs") / run_id / "output" / "scan_result.canonical.v1.json"
{indent}    if canon_p.exists():
{indent}        import json as _json
{indent}        canon = _json.loads(canon_p.read_text(encoding="utf-8"))
{indent}        items = canon.get("items") or canon.get("files") or []
{indent}        junk_ext = set([".tmp", ".bak", ".old"])
{indent}        large_min = 10 * 1024 * 1024  # 10MB
{indent}        findings_local = []
{indent}        for it in items:
{indent}            p = str(it.get("path") or "")
{indent}            sz = int(it.get("size") or 0)
{indent}            ext = Path(p).suffix.lower()
{indent}            if ext in junk_ext:
{indent}                findings_local.append({{
{indent}                    "code": "JUNK_EXTENSION",
{indent}                    "severity": "LOW",
{indent}                    "path": p,
{indent}                    "detail": {{"ext": ext, "size": sz}}
{indent}                }})
{indent}            elif sz >= large_min:
{indent}                findings_local.append({{
{indent}                    "code": "LARGE_FILE",
{indent}                    "severity": "MEDIUM",
{indent}                    "path": p,
{indent}                    "detail": {{"size": sz, "min_bytes": large_min}}
{indent}                }})
{indent}
{indent}        # merge into existing findings if present
{indent}        try:
{indent}            if "findings" in out and isinstance(out.get("findings"), list):
{indent}                out["findings"].extend(findings_local)
{indent}            else:
{indent}                out["findings"] = findings_local
{indent}        except Exception:
{indent}            # if variable name isn't 'out', try common alternatives
{indent}            pass
{indent}
{indent}        # also keep a small summary hint (non-breaking)
{indent}        try:
{indent}            sm = out.get("summary") if isinstance(out.get("summary"), dict) else {{}}
{indent}            sm.setdefault("totals", {{}})
{indent}            sm["totals"]["findings"] = len(out.get("findings") or [])
{indent}            out["summary"] = sm
{indent}        except Exception:
{indent}            pass
{indent}except Exception:
{indent}    pass

"""

# Insert right before the matched line
txt2 = txt[:m.start()] + inject + txt[m.start():]
rp.write_text(txt2, encoding="utf-8")
print("PATCHED run_verdict_stage.py OK (findings rules v1)")
