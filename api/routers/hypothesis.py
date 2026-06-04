"""Hypothesis Engine (THE) endpoints.

Generates structured falsifiable hypotheses about observed system state.
LLM generates hypotheses; deterministic mechanism validates them.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import repository
from api.routers._shared import limiter

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
@limiter.limit("10/minute")
def generate_hypotheses(
    request: Request,
    bundle: EvidenceBundle,
    db: Session = Depends(get_db),
):
    from engine.hypothesis import generate_hypotheses
    result = generate_hypotheses(bundle.model_dump(), db)
    return result


@router.get("/search")
def search_hypotheses(
    cluster: Optional[str] = None,
    failure_class: Optional[str] = None,
    validation: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Search and filter hypotheses."""
    from db.models import HypothesisRecord
    query = db.query(HypothesisRecord)

    if cluster:
        query = query.filter(HypothesisRecord.evidence_snapshot['cluster_name'].astext == cluster)
    if failure_class:
        query = query.filter(HypothesisRecord.evidence_snapshot['failure_class'].astext == failure_class)
    if validation == "pending":
        query = query.filter(HypothesisRecord.validation_outcome.is_(None))
    elif validation == "validated":
        query = query.filter(HypothesisRecord.validation_outcome == "validated")
    elif validation == "falsified":
        query = query.filter(HypothesisRecord.validation_outcome == "falsified")
    if q:
        query = query.filter(HypothesisRecord.claim.ilike(f"%{q}%"))

    total = query.count()
    records = query.order_by(HypothesisRecord.created_at.desc()).limit(limit).all()

    return {
        "hypotheses": [
            {
                "hypothesis_id": r.hypothesis_id,
                "claim": r.claim,
                "testable_conditions": r.testable_conditions or [],
                "confidence_score": r.confidence_score,
                "geometric_stability_score": r.geometric_stability_score,
                "geometric_stability_state": r.geometric_stability_state.value if r.geometric_stability_state else "",
                "validation_outcome": r.validation_outcome.value if r.validation_outcome else None,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "cluster": r.evidence_snapshot.get("cluster_name", "") if r.evidence_snapshot else "",
                "failure_class": r.evidence_snapshot.get("failure_class", "") if r.evidence_snapshot else "",
            }
            for r in records
        ],
        "total": total,
        "filtered": bool(cluster or failure_class or validation or q),
    }


@router.get("/stats")
def get_hypothesis_stats(db: Session = Depends(get_db)):
    """Aggregated hypothesis stats for filtering UI."""
    from db.models import HypothesisRecord
    from sqlalchemy import func, text

    total = db.query(func.count(HypothesisRecord.id)).scalar() or 0
    pending = db.query(func.count(HypothesisRecord.id)).filter(HypothesisRecord.validation_outcome.is_(None)).scalar() or 0
    validated = db.query(func.count(HypothesisRecord.id)).filter(HypothesisRecord.validation_outcome == "validated").scalar() or 0
    falsified = db.query(func.count(HypothesisRecord.id)).filter(HypothesisRecord.validation_outcome == "falsified").scalar() or 0

    clusters = []
    try:
        rows = db.execute(text("""
            SELECT evidence_snapshot->>'cluster_name' as cluster, COUNT(*) as c
            FROM glx_hypotheses WHERE evidence_snapshot IS NOT NULL
            GROUP BY cluster ORDER BY c DESC LIMIT 15
        """)).fetchall()
        clusters = [{"name": r[0] or "unknown", "count": r[1]} for r in rows]
    except Exception:
        pass

    failure_classes = []
    try:
        rows = db.execute(text("""
            SELECT evidence_snapshot->>'failure_class' as fc, COUNT(*) as c
            FROM glx_hypotheses WHERE evidence_snapshot IS NOT NULL AND evidence_snapshot->>'failure_class' != ''
            GROUP BY fc ORDER BY c DESC LIMIT 15
        """)).fetchall()
        failure_classes = [{"name": r[0] or "unknown", "count": r[1]} for r in rows]
    except Exception:
        pass

    return {
        "total": total,
        "pending": pending,
        "validated": validated,
        "falsified": falsified,
        "clusters": clusters,
        "failure_classes": failure_classes,
    }


@router.get("/queue", response_model=HypothesisQueueResponse)
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
    return {
        "hypothesis_id": record.hypothesis_id,
        "claim": record.claim,
        "testable_conditions": record.testable_conditions or [],
        "confidence_score": record.confidence_score,
        "geometric_stability_score": record.geometric_stability_score,
        "geometric_stability_state": record.geometric_stability_state.value if record.geometric_stability_state else "",
        "validation_outcome": record.validation_outcome.value if record.validation_outcome else None,
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "evidence_bundle_id": record.evidence_bundle_id,
        "evidence_snapshot": record.evidence_snapshot,
        "stale": record.stale,
    }


@router.post("/{hypothesis_id}/validate")
@limiter.limit("30/minute")
def validate_hypothesis(
    request: Request,
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
