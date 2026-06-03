"""Hypothesis Engine (THE) endpoints.

Generates structured falsifiable hypotheses about observed system state.
LLM generates hypotheses; deterministic mechanism validates them.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository

router = APIRouter(prefix="/hypotheses", tags=["hypothesis-engine"])


class EvidenceBundle(BaseModel):
    bundle_id: str
    cluster_id: str
    timestamp: str
    collector_source: str
    evidence_fields: dict


class HypothesisResponse(BaseModel):
    hypothesis_id: str
    claim: str
    testable_conditions: list
    confidence_score: float
    geometric_stability_score: float
    geometric_stability_state: str
    validation_outcome: Optional[str] = None
    created_at: str


class HypothesisQueueResponse(BaseModel):
    hypotheses: list[HypothesisResponse]
    total: int


class ValidationRequest(BaseModel):
    hypothesis_id: str
    outcome: str  # validated, falsified, inconclusive
    evidence: Optional[dict] = None


@router.post("/generate", status_code=201)
def generate_hypotheses(
    bundle: EvidenceBundle,
    db: Session = Depends(get_db),
):
    from engine.hypothesis import generate_hypotheses
    result = generate_hypotheses(bundle.model_dump(), db)
    return result


@router.get("/queue")
def get_hypothesis_queue(
    evidence_bundle_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    records = repository.get_hypothesis_queue(db, evidence_bundle_id=evidence_bundle_id, limit=limit)
    return HypothesisQueueResponse(
        hypotheses=[
            HypothesisResponse(
                hypothesis_id=r.hypothesis_id,
                claim=r.claim,
                testable_conditions=r.testable_conditions or [],
                confidence_score=r.confidence_score,
                geometric_stability_score=r.geometric_stability_score,
                geometric_stability_state=r.geometric_stability_state.value if r.geometric_stability_state else "",
                validation_outcome=r.validation_outcome.value if r.validation_outcome else None,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ],
        total=len(records),
    )


@router.get("/{hypothesis_id}")
def get_hypothesis(
    hypothesis_id: str,
    db: Session = Depends(get_db),
):
    record = repository.get_hypothesis(db, hypothesis_id)
    if not record:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return HypothesisResponse(
        hypothesis_id=record.hypothesis_id,
        claim=record.claim,
        testable_conditions=record.testable_conditions or [],
        confidence_score=record.confidence_score,
        geometric_stability_score=record.geometric_stability_score,
        geometric_stability_state=record.geometric_stability_state.value if record.geometric_stability_state else "",
        validation_outcome=record.validation_outcome.value if record.validation_outcome else None,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


@router.post("/{hypothesis_id}/validate")
def validate_hypothesis(
    hypothesis_id: str,
    body: ValidationRequest,
    db: Session = Depends(get_db),
):
    if body.outcome not in ("validated", "falsified", "inconclusive"):
        raise HTTPException(status_code=400, detail="outcome must be: validated, falsified, or inconclusive")
    record = repository.update_hypothesis_validation(db, hypothesis_id, body.outcome)
    if not record:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    db.commit()
    return {"hypothesis_id": hypothesis_id, "validation_outcome": body.outcome}
