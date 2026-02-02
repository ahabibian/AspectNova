from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict


ALLOWED_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}
DEFAULT_RISK_LEVEL = "LOW"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"[normalize_risk_v1] Input not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise SystemExit(f"[normalize_risk_v1] Failed to read JSON: {path} ({e})")
    if not isinstance(data, dict):
        raise SystemExit(f"[normalize_risk_v1] Root must be an object: {path}")
    return data


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_notes_str(value: Any) -> str:
    """
    Normalize notes into a single string (schema-safe).
    Accepts: str, list[str], None, other -> stringified.
    - None -> ""
    - list -> join non-empty parts with "; "
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        parts = []
        for x in value:
            if x is None:
                continue
            if isinstance(x, str):
                s = x.strip()
                if s:
                    parts.append(s)
            else:
                s = str(x).strip()
                if s:
                    parts.append(s)
        return "; ".join(parts)

    return str(value).strip()


def _normalize_level(level: Any) -> str:
    """
    Convert various level forms to one of LOW/MEDIUM/HIGH.
    Rules:
    - NONE/NULL/"" -> LOW
    - case-insensitive strings accepted if matches allowed
    - unknown -> LOW (safe default)
    """
    if level is None:
        return DEFAULT_RISK_LEVEL

    if isinstance(level, str):
        raw = level.strip().upper()
        if raw in ("", "NONE", "NULL", "UNSET", "N/A"):
            return DEFAULT_RISK_LEVEL
        if raw in ALLOWED_RISK_LEVELS:
            return raw

        # Common synonyms
        if raw in ("LOW_RISK", "L"):
            return "LOW"
        if raw in ("MED", "MID", "M"):
            return "MEDIUM"
        if raw in ("HI", "H"):
            return "HIGH"

        return DEFAULT_RISK_LEVEL

    return DEFAULT_RISK_LEVEL


def normalize_command_plan(doc: Dict[str, Any], *, strict: bool) -> Dict[str, Any]:
    """
    Normalize risk objects inside a command_plan (v1) to be schema-safe.
    Key fix: risk.notes MUST be string (not list).
    """
    commands = doc.get("commands")
    if isinstance(commands, list):
        for cmd in commands:
            if not isinstance(cmd, dict):
                continue

            risk = cmd.get("risk")

            # Ensure risk is an object
            if not isinstance(risk, dict):
                cmd["risk"] = {"level": DEFAULT_RISK_LEVEL, "notes": _to_notes_str(risk)}
                risk = cmd["risk"]

            # note -> notes (string)
            if "notes" not in risk and "note" in risk:
                risk["notes"] = _to_notes_str(risk.get("note"))
                risk.pop("note", None)
            else:
                risk["notes"] = _to_notes_str(risk.get("notes"))

            # level normalize
            risk["level"] = _normalize_level(risk.get("level"))

    # IMPORTANT: when strict=True we don't add any extra fields (root may forbid additional props).
    if not strict:
        meta = doc.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            doc["meta"] = meta
        meta.setdefault("risk_normalized_at", _now_iso())
        meta.setdefault("risk_normalizer", {"id": "normalize_risk_v1", "version": "1.1"})

    return doc


def normalize_execution_report(doc: Dict[str, Any], *, strict: bool) -> Dict[str, Any]:
    """
    Normalize risk_level in execution_report (v1).
    - results[*].risk_level: NONE -> LOW
    """
    results = doc.get("results")
    if isinstance(results, list):
        for r in results:
            if not isinstance(r, dict):
                continue

            if "risk_level" in r:
                r["risk_level"] = _normalize_level(r.get("risk_level"))
            else:
                # Fallback: nested risk object
                risk = r.get("risk")
                if isinstance(risk, dict) and "level" in risk:
                    r["risk_level"] = _normalize_level(r.get("level"))
                elif isinstance(risk, dict) and "risk_level" in risk:
                    r["risk_level"] = _normalize_level(r.get("risk_level"))

    if not strict:
        meta = doc.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            doc["meta"] = meta
        meta.setdefault("risk_normalized_at", _now_iso())
        meta.setdefault("risk_normalizer", {"id": "normalize_risk_v1", "version": "1.1"})

    return doc


def detect_type(doc: Dict[str, Any]) -> str:
    if isinstance(doc.get("commands"), list):
        return "command_plan"
    if isinstance(doc.get("results"), list):
        return "execution_report"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize risk fields to be schema-safe (v1).")
    ap.add_argument("in_json", help="input json path")
    ap.add_argument("out_json", help="output json path")
    ap.add_argument(
        "--type",
        choices=["auto", "command_plan", "execution_report"],
        default="auto",
        help="document type (default: auto detect)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="do not add any extra metadata fields (safe for schemas that disallow additional root properties)",
    )
    args = ap.parse_args()

    in_path = Path(args.in_json)
    out_path = Path(args.out_json)

    doc = _load_json(in_path)

    dtype = args.type
    if dtype == "auto":
        dtype = detect_type(doc)

    if dtype == "unknown":
        raise SystemExit(
            "[normalize_risk_v1] Could not detect document type. Use --type command_plan or --type execution_report."
        )

    if dtype == "command_plan":
        doc = normalize_command_plan(doc, strict=args.strict)
    else:
        doc = normalize_execution_report(doc, strict=args.strict)

    _write_json(out_path, doc)
    print(f"[normalize_risk_v1] OK -> wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
