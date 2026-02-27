from pathlib import Path
import sys
from stages.approval.approve import build_approval


def main():
    if len(sys.argv) < 2:
        print("usage: python .\\run_approval_stage.py <run_id> [APPROVE|REJECT] [reason]")
        raise SystemExit(2)

    run_id = sys.argv[1]
    decision = sys.argv[2] if len(sys.argv) >= 3 else "APPROVE"
    reason = sys.argv[3] if len(sys.argv) >= 4 else None

    base = Path("runs") / run_id / "output" / "evidence"
    res = build_approval(run_id=run_id, base_evidence_dir=base, decision=decision, reason=reason)
    print("APPROVAL STAGE DONE:", res)


if __name__ == "__main__":
    main()
