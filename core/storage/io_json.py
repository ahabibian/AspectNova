from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> Any:
    """
    Read JSON with BOM-safe UTF-8 decoding.
    """
    p = Path(path)
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
