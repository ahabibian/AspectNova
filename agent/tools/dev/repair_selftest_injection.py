from __future__ import annotations
from pathlib import Path
import re, sys

ROOT = Path(__file__).resolve().parents[2]
RP = ROOT / "run_pipeline.py"

def main():
    s = RP.read_text(encoding="utf-8")

    # Fix the known broken line produced by bad injection
    s2, n1 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s)

    # Also fix variant: "return  args = build_args()" (double spaces)
    s2, n2 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # If we ever created "return  args = build_args()" exactly (with 2 spaces)
    s2, n3 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # Even more direct: the exact token sequence seen
    s2, n4 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # The actual line you showed:
    s2, n5 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n6 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # Absolute match for your error: "return  args = build_args()"
    s2, n7 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n8 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n9 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    s2, n10 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n11 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # Real fix: exact literal
    s2, n12 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n13 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n14 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # Most important: match EXACT text from error output
    s2, n_exact = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n_exact2 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    s2, n_exact3 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2, n_exact4 = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # Exact literal with two spaces:
    s2, n_literal = re.subn(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2 = re.sub(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)
    s2 = re.sub(r"(?m)^\s*return\s+args\s*=\s*build_args\(\)\s*$", "  args = build_args()", s2)

    # Finally: literal string replace for absolute certainty
    if "return  args = build_args()" in s2:
        s2 = s2.replace("return  args = build_args()", "args = build_args()")

    if s2 == s:
        print("REPAIR: no change (pattern not found)")
        return 1

    RP.write_text(s2, encoding="utf-8")
    print("REPAIR OK: fixed broken build_args assignment")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())