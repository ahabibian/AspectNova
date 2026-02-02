from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def get_plan_key(plan: Dict[str, Any]) -> str:
    idem = plan.get("idempotency") or {}
    pk = (
        idem.get("plan_key")
        or idem.get("key")
        or plan.get("plan_key")
    )
    if not pk or not isinstance(pk, str):
        raise SystemExit("ERROR: command plan missing idempotency.plan_key (or idempotency.key).")
    return pk


def sign(secret: str, msg: str) -> str:
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command_plan_json")
    ap.add_argument("approval_token_out_json")
    ap.add_argument("--approved-by", required=True)
    ap.add_argument("--expires-min", type=int, default=30)
    ap.add_argument("--approve-all", action="store_true")
    args = ap.parse_args()

    secret = os.environ.get("ASPECTNOVA_APPROVAL_SECRET", "")
    if not secret:
        raise SystemExit("ERROR: ASPECTNOVA_APPROVAL_SECRET is not set in environment.")

    plan = read_json(args.command_plan_json)
    plan_key = get_plan_key(plan)

    now = _dt.datetime.now(_dt.timezone.utc)
    exp = now + _dt.timedelta(minutes=int(args.expires_min))

    token_payload = {
        "schema_id": "aspectnova.approval_token",
        "schema_version": "v2",
        "generated_at": utc_now_iso(),
        "approved_by": args.approved_by,
        "expires_at": exp.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "plan_key": plan_key,
        "approve_all": bool(args.approve_all),
    }

    sig = sign(secret, json.dumps(token_payload, sort_keys=True, ensure_ascii=True))
    token_payload["signature"] = sig

    write_json(args.approval_token_out_json, token_payload)
    print(f"[make_approval_token] OK -> wrote: {args.approval_token_out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
