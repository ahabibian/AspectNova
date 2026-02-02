from __future__ import annotations

import argparse
import hmac
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict


TOOL_NAME = "verify_approval_token"
TOOL_VERSION = "approval.verify.v1"


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def hmac_sha256(secret: str, data: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()


def parse_utc(ts: str) -> datetime:
    # expects ...Z
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("approval_token_json", help="Input: out/approval_token.json")
    ap.add_argument("--plan-key", default="", help="Optional: require token for this plan_key")
    ap.add_argument("--command-id", default="", help="Optional: require token covers this command_id")
    args = ap.parse_args()

    token = read_json(args.approval_token_json)

    if token.get("schema_id") != "aspectnova.approval_token":
        print("[verify_approval_token] FAIL: schema_id mismatch")
        return 2
    if token.get("schema_version") != "aspectnova.approval_token.v1":
        print("[verify_approval_token] FAIL: schema_version mismatch")
        return 2

    secret = os.getenv("ASPECTNOVA_APPROVAL_SECRET", "").strip()
    if not secret:
        print("[verify_approval_token] FAIL: Missing ASPECTNOVA_APPROVAL_SECRET")
        return 2

    sig = (token.get("signature") or {}).get("value") or ""
    if not sig:
        print("[verify_approval_token] FAIL: Missing signature.value")
        return 2

    body = {k: token[k] for k in token.keys() if k != "signature"}
    expected = hmac_sha256(secret, canonical_json(body))
    if not hmac.compare_digest(expected, sig):
        print("[verify_approval_token] FAIL: signature mismatch")
        return 2

    tk = token.get("token") or {}
    try:
        expires_at = parse_utc(str(tk.get("expires_at", "")))
        now = datetime.now(timezone.utc)
        if now >= expires_at:
            print("[verify_approval_token] FAIL: token expired")
            return 2
    except Exception:
        print("[verify_approval_token] FAIL: invalid expires_at")
        return 2

    if args.plan_key:
        if str(tk.get("plan_key", "")).strip() != args.plan_key.strip():
            print("[verify_approval_token] FAIL: plan_key mismatch")
            return 2

    if args.command_id:
        approve_all = bool(tk.get("approve_all", False))
        approved = tk.get("approved_commands") or []
        if not approve_all and str(args.command_id) not in set(map(str, approved)):
            print("[verify_approval_token] FAIL: command_id not approved by token")
            return 2

    print("[verify_approval_token] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
