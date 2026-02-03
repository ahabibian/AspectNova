# api/main.py
from __future__ import annotations

from fastapi import FastAPI
from api.routers.runs import router as runs_router

app = FastAPI(title="AspectNova API", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(runs_router)
