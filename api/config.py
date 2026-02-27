from __future__ import annotations

import os
from pathlib import Path


def get_project_root() -> Path:
    """
    Returns the server-side project root path.
    Must be configured via ASPECTNOVA_ROOT.
    """
    val = os.environ.get("ASPECTNOVA_ROOT")
    if not val:
        raise RuntimeError("ASPECTNOVA_ROOT is not set")
    return Path(val).resolve()
