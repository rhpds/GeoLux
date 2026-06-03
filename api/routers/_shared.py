"""Shared state, configuration, and dependencies for GeoLux routers."""

import os
import threading
import time
from typing import Optional

from fastapi import Depends, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from db.database import get_db

# ── Configuration ─────────────────────────────────────────────────────

GEOLUX_MODE = os.environ.get("GEOLUX_MODE", "live")
VALID_MODES = ("live", "synthetic", "replay")

STABILITY_THRESHOLD = float(os.environ.get("GEOLUX_STABILITY_THRESHOLD", "0.7"))
STABILITY_METHOD = os.environ.get("GEOLUX_STABILITY_METHOD", "token_probability")
STABILITY_THRESHOLDS = {
    "hypothesis_generation": float(os.environ.get("GEOLUX_STABILITY_THRESHOLD_HYPOTHESIS", str(STABILITY_THRESHOLD))),
    "semantic_classification": float(os.environ.get("GEOLUX_STABILITY_THRESHOLD_CLASSIFICATION", str(STABILITY_THRESHOLD))),
    "mpc_prediction": float(os.environ.get("GEOLUX_STABILITY_THRESHOLD_MPC", str(STABILITY_THRESHOLD))),
    "mpc_optimization": float(os.environ.get("GEOLUX_STABILITY_THRESHOLD_MPC", str(STABILITY_THRESHOLD))),
    "deepfield_classification": float(os.environ.get("GEOLUX_STABILITY_THRESHOLD_DEEPFIELD", str(STABILITY_THRESHOLD))),
}

MPC_DEFAULT_HORIZON = int(os.environ.get("GEOLUX_MPC_HORIZON", "2"))
MPC_MAX_HORIZON = int(os.environ.get("GEOLUX_MPC_MAX_HORIZON", "5"))
MPC_MIN_HISTORY_WEEKS = int(os.environ.get("GEOLUX_MPC_MIN_HISTORY_WEEKS", "4"))

CONFIDENCE_THRESHOLD = float(os.environ.get("GEOLUX_CONFIDENCE_THRESHOLD", "0.7"))

LITELLM_URL = os.environ.get("GEOLUX_LITELLM_URL", os.environ.get("STARGATE_LITELLM_URL", ""))
LITELLM_API_KEY = os.environ.get("GEOLUX_LITELLM_API_KEY", os.environ.get("STARGATE_LITELLM_API_KEY", ""))
LLM_MODEL = os.environ.get("GEOLUX_LLM_MODEL", os.environ.get("STARGATE_LLM_MODEL", "granite-3-2-8b-instruct"))

GAUDI_URL = os.environ.get("GEOLUX_GAUDI_URL", os.environ.get("STARGATE_GAUDI_URL", ""))
XEON6_URL = os.environ.get("GEOLUX_XEON6_URL", os.environ.get("STARGATE_XEON6_URL", ""))

ADMIN_API_KEY = os.environ.get("GEOLUX_ADMIN_API_KEY", os.environ.get("STARGATE_ADMIN_API_KEY", ""))

# ── Rate Limiter ──────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

# ── Auth ──────────────────────────────────────────────────────────────


def require_admin(request):
    api_key = request.headers.get("X-API-Key", "")
    proxy_user = request.headers.get("X-Forwarded-User", "")
    if ADMIN_API_KEY and api_key == ADMIN_API_KEY:
        return api_key
    if proxy_user:
        return proxy_user
    raise HTTPException(status_code=401, detail="Admin access required")


# ── Shutdown Event ────────────────────────────────────────────────────

_shutdown_event = threading.Event()

# ── TTL Cache ─────────────────────────────────────────────────────────

_constraint_cache: dict = {"data": None, "ts": 0.0}
CONSTRAINT_CACHE_TTL = 300

_view_cache: dict = {"stability": {}, "hypothesis": {}, "classification": {}, "ts": 0.0}
VIEW_CACHE_TTL = 60


def get_cached_constraints(db):
    """Get constraint definitions with TTL cache."""
    now = time.time()
    if _constraint_cache["data"] is not None and now - _constraint_cache["ts"] < CONSTRAINT_CACHE_TTL:
        return _constraint_cache["data"]
    from db import repository
    data = repository.get_constraint_definitions(db)
    _constraint_cache["data"] = data
    _constraint_cache["ts"] = now
    return data


def invalidate_constraint_cache():
    _constraint_cache["data"] = None
    _constraint_cache["ts"] = 0.0
