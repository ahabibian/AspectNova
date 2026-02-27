from pathlib import Path

WATCH = [
 "run_pipeline.py",
 "run_manifest_stage.py",
 "run_integrity_stage.py",
 "run_execution_stage.py",
 "run_approval_stage.py"
]

BOM = b"\xef\xbb\xbf"

def main():
    root = Path(".")
    fixed = []
    clean = []
    missing = []

    for f in WATCH:
        p = root / f
        if not p.exists():
            missing.append(f)
            continue

        data = p.read_bytes()
        if data.startswith(BOM):
            p.write_bytes(data[len(BOM):])
            fixed.append(f)
        else:
            clean.append(f)

    print("STRIP_BOM DONE")
    print("fixed:", fixed)
    print("clean:", clean)
    if missing:
        print("missing:", missing)

if __name__ == "__main__":
    main()