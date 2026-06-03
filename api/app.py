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

import threading

from db.database import init_db
from api.routers._shared import limiter, GEOLUX_MODE, _shutdown_event

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


def _view_refresh_loop():
    """Background thread: refresh materialized view caches every 60s."""
    import time
    time.sleep(5)
    lgr = logging.getLogger("geolux.views")
    while not _shutdown_event.is_set():
        try:
            from db.database import get_db
            from db.views import refresh_stability_summary, refresh_hypothesis_metrics, refresh_classification_rates
            from api.routers._shared import _view_cache
            db = next(get_db())
            _view_cache["stability"] = refresh_stability_summary(db)
            _view_cache["hypothesis"] = refresh_hypothesis_metrics(db)
            _view_cache["classification"] = refresh_classification_rates(db)
            _view_cache["ts"] = time.time()
            db.close()
            lgr.debug("View refresh complete")
        except Exception as e:
            lgr.debug("View refresh failed: %s", e)
        _shutdown_event.wait(60)


def _retention_loop():
    """Background thread: run data retention cleanup daily."""
    import time
    time.sleep(3600)
    lgr = logging.getLogger("geolux.retention")
    while not _shutdown_event.is_set():
        try:
            from db.database import get_db
            from engine.retention import RetentionManager
            db = next(get_db())
            result = RetentionManager().run(db)
            lgr.info("Retention cleanup: %s", result)
            db.close()
        except Exception as e:
            lgr.debug("Retention cleanup failed: %s", e)
        _shutdown_event.wait(86400)


def _launchpad_refresh_loop():
    """Background thread: fetch RHDP data from Stargate and compute intelligence."""
    import time as _t
    import json
    import urllib.request
    _t.sleep(30)
    lgr = logging.getLogger("geolux.launchpad")
    while not _shutdown_event.is_set():
        try:
            sg_base = os.environ.get("STARGATE_API_URL", "http://stargate-api.stargate.svc:8090")
            admin_key = os.environ.get("GEOLUX_ADMIN_API_KEY", os.environ.get("STARGATE_ADMIN_API_KEY", ""))
            headers = {"X-API-Key": admin_key} if admin_key else {}

            labs_data = {}
            for ep in ["/dashboard/overview"]:
                try:
                    req = urllib.request.Request(f"{sg_base}{ep}", headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        labs_data = json.loads(resp.read())
                except Exception:
                    pass

            if labs_data:
                from db.database import get_db
                from engine.launchpad import LaunchpadIntelligence
                db = next(get_db())
                intel = LaunchpadIntelligence()
                labs = labs_data.get("labs", {})
                sessions = [{"demo_id": l.get("lab_code", ""), "partner_id": "", "sa_id": "", "lab_code": l.get("lab_code", ""), "config": "", "status": l.get("status", ""), "cost": 0, "hardware_config": "cpu", "started_at": ""} for l in labs.get("details", [])] if isinstance(labs.get("details"), list) else []
                if sessions:
                    intel.compute_demand_signals({"sessions": sessions, "labs": [{"lab_code": s["lab_code"]} for s in sessions]}, db)
                    lgr.info("Launchpad intelligence refreshed: %d sessions", len(sessions))
                db.close()
        except Exception as e:
            lgr.debug("Launchpad refresh failed: %s", e)
        _shutdown_event.wait(300)


_kafka_consumer_manager = None


def _start_kafka_consumers():
    """Start Kafka consumer threads for all GeoLux topics + stargate-evaluations."""
    global _kafka_consumer_manager
    lgr = logging.getLogger("geolux.kafka")
    kafka_brokers = os.environ.get("GEOLUX_KAFKA_BROKERS", "")
    if not kafka_brokers:
        lgr.info("Kafka not configured — consumers not started")
        return

    try:
        from events.consumers import KafkaConsumerManager

        _kafka_consumer_manager = KafkaConsumerManager(group_id="geolux-consumers")

        def _handle_stargate_evaluation(message: dict):
            """Process Stargate evaluation events through GeoLux pipeline."""
            try:
                payload = message.get("payload", message)
                from api.routers.integration import StarGateEvent, process_stargate_event
                from db.database import get_db
                db = next(get_db())
                event = StarGateEvent(
                    source="stargate-kafka",
                    event_type=message.get("event_type", "evaluation.unknown"),
                    event_id=message.get("event_id"),
                    timestamp=message.get("_published_at", message.get("timestamp")),
                    payload=payload if isinstance(payload, dict) else {"raw": payload},
                )
                result = process_stargate_event(event, db)
                db.close()
                lgr.info("Kafka event processed: %s → %s", event.event_type, result.classification_result)
            except Exception as e:
                lgr.warning("Stargate evaluation handler error: %s", e)

        _kafka_consumer_manager.register_handler("stargate-evaluations", _handle_stargate_evaluation)

        from events.consumers import (
            _handle_evidence_collected,
            _handle_hypothesis_generated,
            _handle_classification_completed,
            _handle_mpc_action_recommended,
        )
        _kafka_consumer_manager.register_handler("geolux-evidence-collected", _handle_evidence_collected)
        _kafka_consumer_manager.register_handler("geolux-hypothesis-generated", _handle_hypothesis_generated)
        _kafka_consumer_manager.register_handler("geolux-classification-completed", _handle_classification_completed)
        _kafka_consumer_manager.register_handler("geolux-mpc-action-recommended", _handle_mpc_action_recommended)

        _kafka_consumer_manager.start()
        lgr.info("Kafka consumers started — brokers=%s, topics=%d", kafka_brokers, len(_kafka_consumer_manager._handlers))

    except ImportError as e:
        lgr.warning("Kafka consumer startup failed (missing library): %s", e)
    except Exception as e:
        lgr.warning("Kafka consumer startup failed: %s", e)


@app.on_event("startup")
def on_startup():
    logger = logging.getLogger("geolux")
    init_db()
    import scenarios.healthy_baseline
    import scenarios.node_failure
    import scenarios.instability_event
    threading.Thread(target=_view_refresh_loop, daemon=True).start()
    threading.Thread(target=_retention_loop, daemon=True).start()
    threading.Thread(target=_launchpad_refresh_loop, daemon=True).start()
    _start_kafka_consumers()
    logger.info(f"GeoLux started — mode={GEOLUX_MODE}")


@app.on_event("shutdown")
def on_shutdown():
    _shutdown_event.set()
    if _kafka_consumer_manager:
        _kafka_consumer_manager.stop()
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
from api.routers.integration import router as integration_router

app.include_router(health_router)
app.include_router(stability_router)
app.include_router(hypothesis_router)
app.include_router(classification_router)
app.include_router(mpc_router)
app.include_router(deepfield_router)
app.include_router(launchpad_router)
app.include_router(scenarios_router)
app.include_router(integration_router)

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
