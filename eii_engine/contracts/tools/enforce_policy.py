from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[enforce_policy] Failed to read JSON: {path} ({e})")


def save_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python contracts/tools/enforce_policy.py <payload.json>", file=sys.stderr)
        raise SystemExit(2)

    payload_path = Path(sys.argv[1]).resolve()
    if not payload_path.exists():
        raise SystemExit(f"[enforce_policy] Payload not found: {payload_path}")

    p = load_json(payload_path)
    if not isinstance(p, dict):
        raise SystemExit("[enforce_policy] Payload root must be an object")

    policy = p.get("policy") or {}
    if not isinstance(policy, dict):
        raise SystemExit("[enforce_policy] policy must be an object")

    data_level = policy.get("data_level", "L1")
    content_allowed = bool(policy.get("content_allowed", False))
    path_handling = policy.get("path_handling", "classified")  # none/tokenized/classified

    # --- HARD RULE 1: No content when content_allowed is false (ADR-001) ---
    if not content_allowed:
        # reject if any item contains "content"
        scan = p.get("scan") or {}
        items = (scan.get("items") or [])
        if isinstance(items, list):
            for i, it in enumerate(items):
                if isinstance(it, dict) and "content" in it:
                    raise SystemExit(
                        f"[enforce_policy] REJECT: content present in item #{i} while content_allowed=false"
                    )

    # --- HARD RULE 2: Data level constraints ---
    if data_level == "L0":
        scan = p.get("scan") or {}
        items = (scan.get("items") or [])
        if isinstance(items, list):
            for i, it in enumerate(items):
                if not isinstance(it, dict):
                    continue
                if "signals" in it or "content" in it:
                    raise SystemExit(f"[enforce_policy] REJECT: L0 payload contains signals/content at item #{i}")

    if data_level == "L1":
        scan = p.get("scan") or {}
        items = (scan.get("items") or [])
        if isinstance(items, list):
            for i, it in enumerate(items):
                if isinstance(it, dict) and "content" in it:
                    raise SystemExit(f"[enforce_policy] REJECT: L1 payload contains content at item #{i}")

    # --- HARD RULE 3: Path handling ---
    # classified => no raw path tokens / name hashes stored
    scan = p.get("scan") or {}
    items = (scan.get("items") or [])
    if path_handling == "classified" and isinstance(items, list):
        # we STRIP these fields (not reject), because classification mode means we keep location_class only
        stripped = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            if "path_token" in it:
                it.pop("path_token", None)
                stripped += 1
            if "name_hash" in it:
                it.pop("name_hash", None)
                stripped += 1
        if stripped:
            # write back sanitized payload
            save_json(payload_path, p)
            print(f"[enforce_policy] SANITIZED: stripped {stripped} path/name fields due to path_handling=classified")
        else:
            print("[enforce_policy] OK: no path/name fields to strip")
    else:
        print("[enforce_policy] OK")

    raise SystemExit(0)


if __name__ == "__main__":
    main()
