from pathlib import Path
import sys
from stages.finalizer.stage import write_final_report

def main():
    if len(sys.argv) < 2:
        print("usage: python .\\run_finalizer_stage.py <run_id>")
        raise SystemExit(2)

    run_id = sys.argv[1]
    out_dir = Path("runs") / run_id / "output" / "evidence"
    policy = Path("policies") / "finalizer.policy.json"

    if not out_dir.exists():
        raise FileNotFoundError(f"missing out_dir: {out_dir}")

    res = write_final_report(run_id=run_id, out_dir=out_dir, policy_path=policy)
    print("FINALIZER STAGE DONE:", res)

if __name__ == "__main__":
    main()