from __future__ import annotations

from fastapi import FastAPI

from api.routers.control import router as control_router
from api.routers.jobs import router as jobs_router
from api.routers.runs import router as runs_router

app = FastAPI(title="AspectNova API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(runs_router)
app.include_router(jobs_router)
app.include_router(control_router)
