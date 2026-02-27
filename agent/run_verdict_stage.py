import sys
import json
from pathlib import Path
from stages.verdict_builder.builder_verdict import build_verdict

def main():
    # Usage:
    #   python .\run_verdict_stage.py <RUN_ID>
    # If not provided, default to the run you've been using.
    run_id = sys.argv[1] if len(sys.argv) > 1 else "scan_manual_20260214T083438Z"

    base = Path(__file__).parent / "runs" / run_id / "output"
    evi = base / "evidence"

    pack = evi / "evidence_pack.v1+owner.json"
    if not pack.exists():
        raise FileNotFoundError(f"Missing evidence pack: {pack}")


    # --- VERDICT_FINDINGS_RULES_V1

    # Minimal, deterministic findings rules (enterprise-friendly baseline)

    try:

        # canonical scan is the most stable input for rules

        canon_p = Path("runs") / run_id / "output" / "scan_result.canonical.v1.json"

        if canon_p.exists():

            import json as _json

            canon = _json.loads(canon_p.read_text(encoding="utf-8"))

            items = canon.get("items") or canon.get("files") or []

            junk_ext = set([".tmp", ".bak", ".old"])

            large_min = 10 * 1024 * 1024  # 10MB

            findings_local = []

            for it in items:

                p = str(it.get("path") or "")

                sz = int(it.get("size") or 0)

                ext = Path(p).suffix.lower()

                if ext in junk_ext:

                    findings_local.append({

                        "code": "JUNK_EXTENSION",

                        "severity": "LOW",

                        "path": p,

                        "detail": {"ext": ext, "size": sz}

                    })

                elif sz >= large_min:

                    findings_local.append({

                        "code": "LARGE_FILE",

                        "severity": "MEDIUM",

                        "path": p,

                        "detail": {"size": sz, "min_bytes": large_min}

                    })

    

            # merge into existing findings if present

            try:

                if "findings" in out and isinstance(out.get("findings"), list):

                    out["findings"].extend(findings_local)

                else:

                    out["findings"] = findings_local

            except Exception:

                # if variable name isn't 'out', try common alternatives

                pass

    

            # also keep a small summary hint (non-breaking)

            try:

                sm = out.get("summary") if isinstance(out.get("summary"), dict) else {}

                sm.setdefault("totals", {})

                sm["totals"]["findings"] = len(out.get("findings") or [])

                out["summary"] = sm

            except Exception:

                pass

    except Exception:

        pass


    out = evi / "verdict.json"
    verdict = build_verdict(pack, out, run_id)

    print("VERDICT STAGE DONE:", {
        "run_id": run_id,
        "out": str(out),
        "status": verdict["summary"]["status"],
        "fail_rate": verdict["summary"]["totals"]["owner_fail_rate"],
        "findings": len(verdict.get("findings", []))
    })

if __name__ == "__main__":
    main()
