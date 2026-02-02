from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def _utc_now_iso_z() -> str:
    # timezone-aware UTC timestamp, RFC3339-ish with Z
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("Artifact JSON root must be an object")
    return obj


def _canonical_json_bytes(obj: Any) -> bytes:
    # stable canonicalization (sort keys + compact separators)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_secret() -> bytes:
    # Choose ONE env name and stick to it; keep backward compatible too.
    secret = (
        os.getenv("EII_HMAC_SECRET")
        or os.getenv("EII_KEY_SECRET")
        or os.getenv("EII_SECRET")
    )
    if not secret:
        # Hard truth: in "real" mode you should NOT default this.
        # But for local pipeline bring-up, we allow a dev default.
        secret = "dev-secret-change-me"
    return secret.encode("utf-8")


def _hmac_hex(secret: bytes, msg: str) -> str:
    return hmac.new(secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _log(msg: str) -> None:
    print(f"[sign_artifact_v1] {msg}")


def build_signature_doc(
    artifact_path: Path,
    artifact_obj: Dict[str, Any],
    key_id: str,
    requested: bool,
    method: str,
) -> Dict[str, Any]:
    artifact_bytes = _canonical_json_bytes(artifact_obj)
    content_hash = _sha256_hex(artifact_bytes)

    signed_at = _utc_now_iso_z()
    # deterministic message that verify can recompute
    sign_payload = f"{content_hash}|{key_id}|{signed_at}|{method}"

    secret = _get_secret()
    sig = _hmac_hex(secret, sign_payload)

    return {
        "artifact": {
            "path": str(artifact_path).replace("\\", "/"),
            "content_hash": content_hash,
        },
        "signature": {
            "key_id": key_id,
            "requested": requested,
            "method": method,
            "signed_at": signed_at,
            "signature": sig,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sign a JSON artifact with HMAC-SHA256.")
    p.add_argument("artifact_json", help="Path to artifact JSON (NOT a .sig.json file).")
    p.add_argument("--out", default=None, help="Output signature path. Default: <artifact>.sig.json")
    p.add_argument("--key-id", default=os.getenv("EII_KEY_ID", "local-dev"), help="Key id (default from EII_KEY_ID).")
    p.add_argument("--requested", type=int, default=int(os.getenv("EII_SIGNATURE_REQUESTED", "1")), help="0 or 1")
    p.add_argument("--method", default="HMAC-SHA256", help="Signature method label")
    args = p.parse_args(argv)

    artifact_path = Path(args.artifact_json)

    if artifact_path.name.endswith(".sig.json"):
        _log("FAIL: Refusing to sign a signature file (*.sig.json). Provide the artifact JSON instead.")
        return 2

    if not artifact_path.exists():
        _log(f"FAIL: file not found: {artifact_path}")
        return 2

    try:
        artifact_obj = _read_json(artifact_path)
    except Exception as e:
        _log(f"FAIL: cannot read JSON: {e}")
        return 2

    out_path = Path(args.out) if args.out else Path(str(artifact_path) + ".sig.json")

    sig_doc = build_signature_doc(
        artifact_path=artifact_path,
        artifact_obj=artifact_obj,
        key_id=str(args.key_id),
        requested=bool(int(args.requested)),
        method=str(args.method),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(sig_doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    _log(f"OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
