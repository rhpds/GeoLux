"""GeoLux API — FastAPI service for governed agentic inference.

Geometric stability, hypothesis generation, constraint classification,
model predictive control, and Deepfield routing.
"""

import logging
import os
import time as _time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from db.database import init_db
from api.routers._shared import limiter, GEOLUX_MODE

app = FastAPI(
    title="GeoLux",
    description="Governed agentic inference platform — geometric stability, hypothesis generation, constraint classification, MPC, and Deepfield routing",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(GZipMiddleware, minimum_size=1000)

_cors_origins = os.environ.get(
    "GEOLUX_CORS_ORIGINS",
    os.environ.get("STARGATE_CORS_ORIGINS", "http://localhost:3000,http://localhost:8090"),
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request.state.request_id = request_id
    start = _time.time()
    response = await call_next(request)
    duration_ms = int((_time.time() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-GeoLux-Mode"] = GEOLUX_MODE
    path = request.url.path
    if path not in ("/health", "/docs", "/redoc", "/openapi.json", "/metrics"):
        logging.getLogger("geolux.http").info(
            f"{request.method} {path} → {response.status_code} ({duration_ms}ms) [{request_id}] mode={GEOLUX_MODE}"
        )
        from api.metrics import http_requests_total, http_request_duration
        http_requests_total.labels(method=request.method, path=path, status=response.status_code).inc()
        http_request_duration.labels(method=request.method, path=path).observe(duration_ms / 1000)
    return response


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@app.on_event("startup")
def on_startup():
    logger = logging.getLogger("geolux")
    init_db()
    logger.info(f"GeoLux started — mode={GEOLUX_MODE}")


@app.on_event("shutdown")
def on_shutdown():
    logging.getLogger("geolux").info("Shutting down GeoLux")


# ── Routers ───────────────────────────────────────────────────────────

from api.routers.health import router as health_router
from api.routers.stability import router as stability_router
from api.routers.hypothesis import router as hypothesis_router
from api.routers.classification import router as classification_router
from api.routers.mpc import router as mpc_router
from api.routers.deepfield import router as deepfield_router
from api.routers.launchpad import router as launchpad_router
from api.routers.scenarios import router as scenarios_router

app.include_router(health_router)
app.include_router(stability_router)
app.include_router(hypothesis_router)
app.include_router(classification_router)
app.include_router(mpc_router)
app.include_router(deepfield_router)
app.include_router(launchpad_router)
app.include_router(scenarios_router)

# Serve frontend static files if dist/ exists (combined deployment)
from pathlib import Path as _Path
_frontend_dist = _Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = (_frontend_dist / full_path).resolve()
        if file_path.is_file() and str(file_path).startswith(str(_frontend_dist.resolve())):
            return FileResponse(file_path)
        return FileResponse(_frontend_dist / "index.html")
