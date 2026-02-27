from __future__ import annotations
from pathlib import Path
import re

fp = Path("run_scan_stage.py")

txt = fp.read_text(encoding="utf-8")

marker = "ABS_PATH_NORMALIZATION"

if marker in txt:
    print("SKIP: already patched")
    raise SystemExit(0)

# پیدا کردن جای درست inject
pat = r'raw\s*=\s*build_raw_payload\(scan_obj\)'

m = re.search(pat, txt)

if not m:
    raise SystemExit("PATCH FAIL: cannot find build_raw_payload line")

inject = r'''

    # --- ABS_PATH_NORMALIZATION (critical for owner_enricher)
    try:
        base = Path(scan_root).resolve()
        items = raw.get("items") or raw.get("files") or []

        for it in items:
            p = str(it.get("path") or "")
            if not p:
                continue

            P = Path(p)

            if not P.is_absolute():
                P = (base / P).resolve()
            else:
                P = P.resolve()

            it["path"] = str(P)

    except Exception:
        pass

'''

txt2 = txt[:m.end()] + inject + txt[m.end():]

fp.write_text(txt2, encoding="utf-8")

print("PATCHED run_scan_stage.py OK (ABS PATH NORMALIZATION)")
