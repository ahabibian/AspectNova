# api/auth/api_key.py
from __future__ import annotations

import os
from fastapi import Header, HTTPException

def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = os.environ.get("ASPECTNOVA_API_KEY")
    if not expected:
        return  # dev mode
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid API key")
