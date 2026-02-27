from __future__ import annotations

from pathlib import Path

def _write_aliases(primary_path: Path, payload: str) -> None:
    """
    Write legacy+new filename aliases for manifest reports.
    We keep both dot and underscore variants to stabilize contracts.
    """
    name = primary_path.name

    aliases = set()

    # dot -> underscore
    aliases.add(name.replace(".", "_"))
    # underscore -> dot for the first two segments we care about
    # e.g. manifest_post_report_json -> (not used). Keep it simple:
    # handle known patterns:
    aliases.add(name.replace("manifest_post", "manifest.post").replace("manifest_pre", "manifest.pre"))

    # also handle report naming if primary already underscore:
    aliases.add(name.replace("manifest_post", "manifest.post").replace("manifest_pre", "manifest.pre"))

    for an in sorted(a for a in aliases if a and a != name):
        ap = primary_path.with_name(an)
        try:
            ap.write_text(payload, encoding="utf-8")
            _write_aliases(ap, payload)
        except Exception:
            pass

import sys, json
from stages.manifest.stage import run as run_manifest

def main():
    if len(sys.argv) < 2:
        print("usage: python .\\run_manifest_stage.py <run_id> [pre|post]")
        raise SystemExit(2)

    run_id = sys.argv[1]
    phase = (sys.argv[2] if len(sys.argv) > 2 else "pre").lower()
    if phase not in ("pre", "post"):
        print("phase must be 'pre' or 'post'")
        raise SystemExit(2)

    out_dir = Path("runs") / run_id / "output" / "evidence"
    policy = Path("policies") / "manifest.policy.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = run_manifest(run_id=run_id, out_dir=out_dir, policy_path=policy)

    # Phase-specific report (keep existing behavior)
    phase_path = out_dir / f"manifest.{phase}.report.json"
    phase_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Canonical contract report (pipeline expects this)
    canonical_path = out_dir / "manifest.report.json"
    canonical_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("MANIFEST STAGE DONE:", {
        "out": str(canonical_path).replace("/", "\\"),
        "phase_out": str(phase_path).replace("/", "\\"),
        "status": report.get("status"),
        "artifact_count": (report.get("summary") or {}).get("artifact_count"),
        "phase": phase
    })

if __name__ == "__main__":
    main()