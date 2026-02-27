from __future__ import annotations

import sys
from pathlib import Path

from stages.owner_enricher.stage import OwnerEnricherStage


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python run_owner_stage.py <run_id>")
        return 2

    run_id = sys.argv[1]
    evidence_dir = Path("runs") / run_id / "output" / "evidence"
    in_pack = evidence_dir / "evidence_pack.v1.json"

    if not in_pack.exists():
        raise FileNotFoundError(f"missing evidence pack: {in_pack}")

    stage = OwnerEnricherStage()
    stats = stage.run(in_pack, evidence_dir, run_id)
    print("OWNER STAGE DONE:", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
