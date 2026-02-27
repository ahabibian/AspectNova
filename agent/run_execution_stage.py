from pathlib import Path
import sys
from stages.execution_engine.executor import run

def main():
    if len(sys.argv) < 2:
        print("usage: python .\\run_execution_stage.py <run_id>")
        raise SystemExit(2)

    run_id = sys.argv[1]
    out_dir = Path("runs") / run_id / "output" / "evidence"
    res = run(run_id=run_id, out_dir=out_dir)
    print("EXECUTION STAGE DONE:", res)

if __name__ == "__main__":
    main()
