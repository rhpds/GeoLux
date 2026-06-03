"""Launchpad intelligence layer endpoints.

Mines provisioning data from RHDP ecosystem and surfaces patterns.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository

router = APIRouter(prefix="/launchpad", tags=["launchpad"])


@router.get("/intelligence")
def get_intelligence(
    intelligence_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    records = repository.get_intelligence_records(db, intelligence_type=intelligence_type, limit=limit)
    return [
        {
            "intelligence_id": r.intelligence_id,
            "intelligence_type": r.intelligence_type,
            "data_payload": r.data_payload,
            "time_window_start": r.time_window_start.isoformat() if r.time_window_start else "",
            "time_window_end": r.time_window_end.isoformat() if r.time_window_end else "",
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in records
    ]


@router.get("/demand")
def get_demand_signals(db: Session = Depends(get_db)):
    records = repository.get_intelligence_records(db, intelligence_type="demand_signal", limit=10)
    return {"demand_signals": [r.data_payload for r in records]}


@router.get("/cost")
def get_cost_attribution(db: Session = Depends(get_db)):
    records = repository.get_intelligence_records(db, intelligence_type="cost_attribution", limit=10)
    return {"cost_attribution": [r.data_payload for r in records]}


@router.get("/utilization")
def get_utilization_patterns(db: Session = Depends(get_db)):
    records = repository.get_intelligence_records(db, intelligence_type="utilization_pattern", limit=10)
    return {"utilization_patterns": [r.data_payload for r in records]}
