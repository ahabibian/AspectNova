from __future__ import annotations
import json, sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"status":"FAIL","where":"gate_scan_stage","reason":"missing_arg","expected":"<scan_result_json_path>"}))
        return 2
    p = Path(sys.argv[1])
    if not p.exists():
        print(json.dumps({"status":"FAIL","where":"gate_scan_stage","reason":"missing_scan_result","path":str(p)}))
        return 3
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"status":"FAIL","where":"gate_scan_stage","reason":"invalid_json","path":str(p),"error":str(e)}))
        return 4
    files = data.get("files") or data.get("items") or []
    if not isinstance(files, list) or len(files) == 0:
        print(json.dumps({"status":"FAIL","where":"gate_scan_stage","reason":"empty_files","path":str(p)}))
        return 5
    print(json.dumps({"status":"OK","where":"gate_scan_stage","path":str(p),"count":len(files)}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())