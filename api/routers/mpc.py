"""LLM-MPC (Model Predictive Control) endpoints.

Applies model predictive control theory to agent decision-making using
LLM reasoning over system state as the dynamics model.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository
from api.routers._shared import MPC_DEFAULT_HORIZON, MPC_MAX_HORIZON

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
def create_mpc_plan(
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
    records = repository.get_mpc_cycles(db, limit=1)
    for r in records:
        if r.cycle_id == cycle_id:
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
