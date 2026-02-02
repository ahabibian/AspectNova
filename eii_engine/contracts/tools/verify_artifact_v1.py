from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


def _log(msg: str) -> None:
    print(f"[verify_artifact_v1] {msg}")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("JSON root must be an object")
    return obj


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_secret() -> bytes:
    secret = (
        os.getenv("EII_HMAC_SECRET")
        or os.getenv("EII_KEY_SECRET")
        or os.getenv("EII_SECRET")
    )
    if not secret:
        secret = "dev-secret-change-me"
    return secret.encode("utf-8")


def _hmac_hex(secret: bytes, msg: str) -> str:
    return hmac.new(secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify an artifact signature created by sign_artifact_v1.")
    p.add_argument("sig_json", help="Path to signature JSON (*.sig.json)")
    p.add_argument("--artifact", default=None, help="Optional explicit artifact JSON path (default: remove .sig.json)")
    args = p.parse_args(argv)

    sig_path = Path(args.sig_json)
    if not sig_path.exists():
        _log(f"FAIL: signature file not found: {sig_path}")
        return 2

    try:
        sig_doc = _read_json(sig_path)
    except Exception as e:
        _log(f"FAIL: cannot read signature JSON: {e}")
        return 2

    artifact_info = sig_doc.get("artifact")
    signature_info = sig_doc.get("signature")

    if not isinstance(artifact_info, dict):
        _log("FAIL: signature doc missing 'artifact' object")
        return 2
    if not isinstance(signature_info, dict):
        _log("FAIL: signature doc missing 'signature' object")
        return 2

    recorded_hash = artifact_info.get("content_hash")
    if not isinstance(recorded_hash, str) or not recorded_hash:
        _log("FAIL: Signature missing 'artifact.content_hash'")
        return 2

    key_id = signature_info.get("key_id")
    method = signature_info.get("method")
    signed_at = signature_info.get("signed_at")
    recorded_sig = signature_info.get("signature")

    for k, v in [("key_id", key_id), ("method", method), ("signed_at", signed_at), ("signature", recorded_sig)]:
        if not isinstance(v, str) or not v:
            _log(f"FAIL: signature missing '{k}'")
            return 2

    # Find artifact json path
    if args.artifact:
        artifact_path = Path(args.artifact)
    else:
        # default: strip one ".sig.json"
        if not sig_path.name.endswith(".sig.json"):
            _log("FAIL: --artifact not provided and signature file does not end with .sig.json")
            return 2
        artifact_path = sig_path.with_name(sig_path.name[: -len(".sig.json")])

    if not artifact_path.exists():
        _log(f"FAIL: artifact file not found: {artifact_path}")
        return 2

    try:
        artifact_obj = _read_json(artifact_path)
    except Exception as e:
        _log(f"FAIL: cannot read artifact JSON: {e}")
        return 2

    computed_hash = _sha256_hex(_canonical_json_bytes(artifact_obj))
    if computed_hash != recorded_hash:
        _log("FAIL: content_hash mismatch")
        _log(f"  recorded: {recorded_hash}")
        _log(f"  computed: {computed_hash}")
        return 1

    # Recompute signature
    payload = f"{recorded_hash}|{key_id}|{signed_at}|{method}"
    secret = _get_secret()
    computed_sig = _hmac_hex(secret, payload)

    if not hmac.compare_digest(computed_sig, recorded_sig):
        _log("FAIL: signature mismatch")
        return 1

    _log("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
