from pathlib import Path
import sys
from stages.integrity_checker.checker import build_integrity_report

def main():
    if len(sys.argv) < 2:
        print("usage: python run_integrity_stage.py <run_id> [post]")
        raise SystemExit(2)

    run_id = sys.argv[1]
    phase = (sys.argv[2] if len(sys.argv) > 2 else "post").lower()

    out_dir = Path("runs") / run_id / "output" / "evidence"
    res = build_integrity_report(run_id=run_id, out_dir=out_dir)
    print("INTEGRITY STAGE DONE:", res)

if __name__ == "__main__":
    main()