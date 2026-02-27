from __future__ import annotations

import sys
from pathlib import Path

from stages.evidence_builder.stage import EvidenceBuilderStage


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python run_evidence_stage.py <run_id>")
        return 2

    run_id = sys.argv[1]
    out_dir = Path("runs") / run_id / "output" / "evidence"
    scan_file = Path("runs") / run_id / "output" / "scan_result.canonical.json"

    if not scan_file.exists():
        raise FileNotFoundError(f"missing scan input: {scan_file}")

    stage = EvidenceBuilderStage()
    result = stage.run(scan_file, out_dir, run_id)
    print("EVIDENCE STAGE DONE:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
