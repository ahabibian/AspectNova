from __future__ import annotations

import sys
from stages.preflight.stage import PreflightStage


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python run_preflight_stage.py <run_id>")
        return 2

    run_id = sys.argv[1]
    st = PreflightStage()
    rep = st.run(run_id=run_id)
    print("PREFLIGHT DONE:", {"status": rep.get("status"), "fixes": len(rep.get("fixes") or [])})
    return 0 if rep.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
