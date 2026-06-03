"""Deepfield routing endpoints.

Governs agent cognitive complexity by mapping task complexity to hardware
substrate as a policy decision.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository

router = APIRouter(prefix="/deepfield", tags=["deepfield"])


class RouteRequest(BaseModel):
    workload_id: str
    workload_description: dict
    current_cluster_state: Optional[dict] = None
    override_tier: Optional[str] = None
    override_reason: Optional[str] = None
    override_operator: Optional[str] = None


class RouteResponse(BaseModel):
    routing_id: str
    workload_id: str
    tier_assignment: str
    substrate: str
    confidence_score: float
    geometric_stability_score: Optional[float] = None
    geometric_stability_state: Optional[str] = None
    policy_rule_applied: Optional[str] = None
    override: bool
    created_at: str


@router.post("/route", status_code=201)
def route_workload(
    body: RouteRequest,
    db: Session = Depends(get_db),
):
    from engine.deepfield import DeepfieldRouter
    router_engine = DeepfieldRouter()
    result = router_engine.route(body.model_dump(), db)
    return result


@router.get("/tiers")
def list_tiers():
    return {
        "tiers": [
            {
                "name": "nano",
                "substrate": "cpu",
                "agent_type": "deterministic, rule-based, boolean evaluation",
                "governance_surface": "minimal",
            },
            {
                "name": "micro",
                "substrate": "xeon6",
                "agent_type": "moderate reasoning, structured inference",
                "governance_surface": "medium",
            },
            {
                "name": "macro",
                "substrate": "gaudi",
                "agent_type": "complex reasoning, long context, multi-step inference",
                "governance_surface": "maximum",
            },
        ]
    }


@router.get("/routing-history")
def get_routing_history(
    workload_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    records = repository.get_routing_decisions(db, workload_id=workload_id, limit=limit)
    return [
        {
            "routing_id": r.routing_id,
            "workload_id": r.workload_id,
            "tier_assignment": r.tier_assignment.value if r.tier_assignment else "",
            "substrate": r.substrate.value if r.substrate else "",
            "confidence_score": r.confidence_score,
            "override": r.override,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in records
    ]
