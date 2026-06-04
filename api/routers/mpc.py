"""LLM-MPC (Model Predictive Control) endpoints.

Applies model predictive control theory to agent decision-making using
LLM reasoning over system state as the dynamics model.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository
from api.routers._shared import MPC_DEFAULT_HORIZON, MPC_MAX_HORIZON, limiter

router = APIRouter(prefix="/mpc", tags=["llm-mpc"])


class MPCPlanRequest(BaseModel):
    cluster_id: str
    current_state: dict
    objective: dict
    horizon: Optional[int] = None


class MPCPlanResponse(BaseModel):
    cycle_id: str
    cluster_id: str
    horizon: int
    predictions: list[dict]
    recommended_action: Optional[dict] = None
    optimization_score: Optional[float] = None
    geometric_stability_profile: dict
    horizon_adjusted: bool
    suspended: bool
    created_at: str


@router.post("/plan", status_code=201)
@limiter.limit("10/minute")
def create_mpc_plan(
    request: Request,
    body: MPCPlanRequest,
    db: Session = Depends(get_db),
):
    from engine.mpc import MPCController
    controller = MPCController(
        default_horizon=MPC_DEFAULT_HORIZON,
        max_horizon=MPC_MAX_HORIZON,
    )
    result = controller.plan(body.model_dump(), db)
    return result


@router.get("/stats")
def get_mpc_stats(db: Session = Depends(get_db)):
    """Aggregated MPC stats for dashboard."""
    from db.models import MPCCycleRecord
    from sqlalchemy import func, text

    total = db.query(func.count(MPCCycleRecord.id)).scalar() or 0
    suspended = db.query(func.count(MPCCycleRecord.id)).filter(MPCCycleRecord.suspended == True).scalar() or 0
    adjusted = db.query(func.count(MPCCycleRecord.id)).filter(MPCCycleRecord.horizon_adjusted == True).scalar() or 0

    clusters = []
    try:
        rows = db.execute(text("""
            SELECT cluster_id, COUNT(*) as cycles,
                   AVG(horizon) as avg_horizon,
                   SUM(CASE WHEN suspended THEN 1 ELSE 0 END) as suspended_count,
                   MAX(created_at) as last_cycle
            FROM glx_mpc_cycles
            GROUP BY cluster_id ORDER BY cycles DESC
        """)).fetchall()
        clusters = [{
            "cluster": r[0], "cycles": r[1], "avg_horizon": round(float(r[2] or 0), 1),
            "suspended": r[3], "last_cycle": r[4].isoformat() if r[4] else "",
        } for r in rows]
    except Exception:
        pass

    return {
        "total": total,
        "active": total - suspended,
        "suspended": suspended,
        "horizon_adjusted": adjusted,
        "clusters": clusters,
    }


@router.get("/cycles")
def list_mpc_cycles(
    cluster_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    records = repository.get_mpc_cycles(db, cluster_id=cluster_id, limit=limit)
    return [
        {
            "cycle_id": r.cycle_id,
            "cluster_id": r.cluster_id,
            "horizon": r.horizon,
            "optimization_score": r.optimization_score,
            "horizon_adjusted": r.horizon_adjusted,
            "suspended": r.suspended,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in records
    ]


@router.get("/cycles/{cycle_id}")
def get_mpc_cycle(
    cycle_id: str,
    db: Session = Depends(get_db),
):
    from db.models import MPCCycleRecord
    r = db.query(MPCCycleRecord).filter(MPCCycleRecord.cycle_id == cycle_id).first()
    if r:
            return {
                "cycle_id": r.cycle_id,
                "cluster_id": r.cluster_id,
                "horizon": r.horizon,
                "current_state": r.current_state,
                "predictions": r.predictions,
                "candidate_actions": r.candidate_actions,
                "selected_action_id": r.selected_action_id,
                "optimization_score": r.optimization_score,
                "geometric_stability_profile": r.geometric_stability_profile,
                "horizon_adjusted": r.horizon_adjusted,
                "suspended": r.suspended,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
    raise HTTPException(status_code=404, detail="MPC cycle not found")


@router.get("/cycles/{cycle_id}/detail")
def get_mpc_cycle_detail(
    cycle_id: str,
    db: Session = Depends(get_db),
):
    """Full cycle detail including predictions and candidate actions."""
    from db.models import MPCCycleRecord
    r = db.query(MPCCycleRecord).filter(MPCCycleRecord.cycle_id == cycle_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="MPC cycle not found")
    return {
        "cycle_id": r.cycle_id,
        "cluster_id": r.cluster_id,
        "horizon": r.horizon,
        "current_state": r.current_state,
        "predictions": r.predictions,
        "candidate_actions": r.candidate_actions,
        "selected_action_id": r.selected_action_id,
        "optimization_score": r.optimization_score,
        "geometric_stability_profile": r.geometric_stability_profile,
        "horizon_adjusted": r.horizon_adjusted,
        "suspended": r.suspended,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }
