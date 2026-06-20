"""Geometric stability measurement endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository
from api.routers._shared import STABILITY_THRESHOLD, limiter
from api.security import require_admin_user, AuthenticatedUser

router = APIRouter(prefix="/stability", tags=["stability"])


class StabilityScoreResponse(BaseModel):
    call_id: str
    endpoint: str
    model: str
    stability_score: float
    stability_method: str
    stability_threshold: float
    stability_state: str
    created_at: str


class StabilityThresholdUpdate(BaseModel):
    threshold: float


@router.get("/scores")
def get_stability_scores(
    endpoint: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    records = repository.get_stability_records(db, endpoint=endpoint, limit=limit)
    return [
        StabilityScoreResponse(
            call_id=r.call_id,
            endpoint=r.endpoint,
            model=r.model,
            stability_score=r.stability_score,
            stability_method=r.stability_method.value if r.stability_method else "",
            stability_threshold=r.stability_threshold,
            stability_state=r.stability_state.value if r.stability_state else "",
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in records
    ]


@router.get("/thresholds")
def get_thresholds():
    return {"stability_threshold": STABILITY_THRESHOLD}


@router.put("/thresholds")
@limiter.limit("5/minute")
def update_thresholds(
    request: Request,
    body: StabilityThresholdUpdate,
    admin: AuthenticatedUser = Depends(require_admin_user),
):
    if not (0.0 <= body.threshold <= 1.0):
        raise HTTPException(status_code=400, detail="Threshold must be between 0.0 and 1.0")
    import api.routers._shared as _shared
    _shared.STABILITY_THRESHOLD = body.threshold
    return {"stability_threshold": body.threshold}
