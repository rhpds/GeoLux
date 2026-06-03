"""Evidence-based constraint classification endpoints.

Classifies system state by evaluating structured evidence against formal
constraint definitions. Classification is deterministic given the evidence.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository

router = APIRouter(prefix="/classify", tags=["classification"])


class ClassifyRequest(BaseModel):
    evidence_bundle_id: str
    evidence: dict
    constraint_ids: Optional[list[str]] = None
    schema_version: Optional[int] = None


class ConstraintResult(BaseModel):
    constraint_id: str
    result: str
    confidence_score: float
    geometric_stability_score: Optional[float] = None
    geometric_stability_state: Optional[str] = None
    evidence_chain: dict
    llm_interpretation_used: bool


class ClassifyResponse(BaseModel):
    classification_id: str
    evidence_bundle_id: str
    results: list[ConstraintResult]
    overall_result: str
    created_at: str


@router.post("", status_code=201)
def classify_evidence(
    body: ClassifyRequest,
    db: Session = Depends(get_db),
):
    from engine.classification import classify_evidence
    result = classify_evidence(body.model_dump(), db)
    return result


@router.get("/constraints")
def list_constraints(
    stage: Optional[str] = None,
    db: Session = Depends(get_db),
):
    records = repository.get_constraint_definitions(db, stage=stage)
    return [
        {
            "constraint_id": r.constraint_id,
            "constraint_name": r.constraint_name,
            "stage": r.stage,
            "assertion_type": r.assertion_type.value if r.assertion_type else "",
            "severity": r.severity.value if r.severity else "",
            "version": r.version,
        }
        for r in records
    ]


@router.get("/classifications/{classification_id}")
def get_classification(
    classification_id: str,
    db: Session = Depends(get_db),
):
    record = repository.get_classification(db, classification_id)
    if not record:
        raise HTTPException(status_code=404, detail="Classification not found")
    return {
        "classification_id": record.classification_id,
        "evidence_bundle_id": record.evidence_bundle_id,
        "constraint_id": record.constraint_id,
        "result": record.result.value if record.result else "",
        "confidence_score": record.confidence_score,
        "geometric_stability_score": record.geometric_stability_score,
        "geometric_stability_state": record.geometric_stability_state.value if record.geometric_stability_state else None,
        "evidence_chain": record.evidence_chain,
        "llm_interpretation_used": record.llm_interpretation_used,
        "created_at": record.created_at.isoformat() if record.created_at else "",
    }
