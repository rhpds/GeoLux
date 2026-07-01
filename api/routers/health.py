"""Health check and mode management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

import api.routers._shared as _shared
from api.security import verify_api_key

router = APIRouter(tags=["health"])


class ModeUpdate(BaseModel):
    mode: str


@router.get("/health")
def health():
    return {"status": "ok", "mode": _shared.GEOLUX_MODE, "service": "geolux"}


@router.get("/mode")
def get_mode():
    return {"mode": _shared.GEOLUX_MODE, "valid_modes": list(_shared.VALID_MODES)}


@router.put("/mode", dependencies=[Depends(verify_api_key)])
def set_mode(body: ModeUpdate):
    if body.mode not in _shared.VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{body.mode}'. Valid modes: {list(_shared.VALID_MODES)}",
        )
    _shared.GEOLUX_MODE = body.mode
    return {"mode": _shared.GEOLUX_MODE}


@router.get("/metrics")
def metrics():
    from api.metrics import get_metrics_response
    content, content_type = get_metrics_response()
    return Response(content=content, media_type=content_type)
