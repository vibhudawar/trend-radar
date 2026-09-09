"""Thin trigger API. The frontend calls POST /projects/{id}/refresh; work runs in the background.
Server-hardening: secrets only from env; generic error responses (no internals leaked); security headers."""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from trendradar.pipeline import run_project

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("trendradar")

app = FastAPI(title="TrendRadar Worker")


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = "default-src 'none'"
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return resp


app.add_middleware(SecurityHeaders)


def _run(project_id: str) -> None:
    try:
        result = run_project(project_id)
        log.info("refresh done: %s credits=%s", result["project_id"], result["credits_used"])
    except Exception:  # noqa: BLE001
        log.exception("refresh failed for project")  # details server-side only


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects/{project_id}/refresh", status_code=202)
def refresh(project_id: str, background: BackgroundTasks) -> JSONResponse:
    background.add_task(_run, project_id)
    return JSONResponse(status_code=202, content={"status": "started", "project_id": project_id})
