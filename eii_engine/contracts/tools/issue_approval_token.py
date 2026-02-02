from __future__ import annotations

import argparse
import hmac
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


TOOL_NAME = "issue_approval_token"
TOOL_VERSION = "approval.issue.v1"


def utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def hmac_sha256(secret: str, data: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command_plan_json", help="Input: out/command_plan.json")
    ap.add_argument("approval_token_json", help="Output: out/approval_token.json")
    ap.add_argument("--approve-all", action="store_true", help="Approve all commands in plan")
    ap.add_argument("--command-id", action="append", default=[], help="Approve specific command_id (repeatable)")
    ap.add_argument("--approved-by", default=os.getenv("ASPECTNOVA_APPROVED_BY", "local-dev"))
    ap.add_argument("--ttl-minutes", type=int, default=int(os.getenv("ASPECTNOVA_APPROVAL_TTL_MIN", "30")))
    ap.add_argument("--reason", default="Approved for execution (confirm-gated).")
    ap.add_argument("--key-id", default=os.getenv("ASPECTNOVA_APPROVAL_KEY_ID", "local-dev"))
    args = ap.parse_args()

    plan = read_json(args.command_plan_json)
    plan_key = (plan.get("idempotency") or {}).get("plan_key") or ""
    if not isinstance(plan_key, str) or len(plan_key.strip()) < 8:
        print("[issue_approval_token] FAIL: plan.idempotency.plan_key missing/invalid")
        return 2

    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        commands = []

    all_ids = []
    for c in commands:
        if isinstance(c, dict) and c.get("command_id"):
            all_ids.append(str(c["command_id"]))

    approve_all = bool(args.approve_all)
    approved_commands: List[str] = []

    if approve_all:
        approved_commands = sorted(set(all_ids))
    else:
        approved_commands = sorted(set([str(x) for x in args.command_id if str(x).strip()]))

    if (not approve_all) and (not approved_commands):
        print("[issue_approval_token] FAIL: Provide --approve-all or at least one --command-id")
        return 2

    secret = os.getenv("ASPECTNOVA_APPROVAL_SECRET", "").strip()
    if not secret:
        print("[issue_approval_token] FAIL: Missing ASPECTNOVA_APPROVAL_SECRET (set an HMAC secret)")
        return 2

    issued_at = utc_now_z()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=max(1, args.ttl_minutes))) \
        .isoformat(timespec="seconds").replace("+00:00", "Z")

    body = {
        "schema_id": "aspectnova.approval_token",
        "schema_version": "aspectnova.approval_token.v1",
        "meta": {
            "generated_at": issued_at,
            "issuer": {"tool": TOOL_NAME, "version": TOOL_VERSION}
        },
        "token": {
            "token_id": f"appr_{uuid.uuid4().hex[:16]}",
            "plan_key": plan_key.strip(),
            "approved_by": str(args.approved_by),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "approve_all": approve_all,
            "approved_commands": approved_commands,
            "reason": str(args.reason)
        }
    }

    sig_payload = canonical_json(body)
    sig = hmac_sha256(secret, sig_payload)

    out = {
        **body,
        "signature": {
            "method": "HMAC-SHA256",
            "key_id": str(args.key_id),
            "signed_at": issued_at,
            "value": sig
        }
    }

    write_json(args.approval_token_json, out)
    print(f"[issue_approval_token] OK -> wrote: {args.approval_token_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
