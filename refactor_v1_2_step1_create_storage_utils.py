from pathlib import Path
import textwrap

ROOT = Path(".").resolve()
STORAGE = ROOT / "core" / "storage"
STORAGE.mkdir(parents=True, exist_ok=True)

io_json = STORAGE / "io_json.py"
hash_utils = STORAGE / "hash_utils.py"

io_json.write_text(textwrap.dedent(r"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> Any:
    """
    Read JSON with BOM-safe UTF-8 decoding.
    """
    p = Path(path)
    # utf-8-sig handles BOM if present
    txt = p.read_text(encoding="utf-8-sig")
    return json.loads(txt)


def write_json(path: str | Path, obj: Any, *, indent: int = 2) -> None:
    """
    Write JSON in canonical pretty format.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(obj, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )
""").lstrip(), encoding="utf-8")

hash_utils.write_text(textwrap.dedent(r"""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
""").lstrip(), encoding="utf-8")

print("OK: wrote", io_json)
print("OK: wrote", hash_utils)

# quick import check
import importlib.util

spec1 = importlib.util.spec_from_file_location("io_json", str(io_json))
m1 = importlib.util.module_from_spec(spec1); spec1.loader.exec_module(m1)
spec2 = importlib.util.spec_from_file_location("hash_utils", str(hash_utils))
m2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(m2)

print("OK: import check passed")
