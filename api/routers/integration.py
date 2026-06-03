"""Integration endpoint for external event sources.

Accepts Stargate evaluation events and feeds them through the
GeoLux processing pipeline: classify → hypothesize → audit.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from api.routers._shared import limiter

logger = logging.getLogger("geolux.integration")

router = APIRouter(prefix="/integration", tags=["integration"])


class StarGateEvent(BaseModel):
    source: str = "stargate"
    event_type: str
    event_id: Optional[str] = None
    timestamp: Optional[str] = None
    payload: dict


class IntegrationResult(BaseModel):
    event_id: str
    processed: bool
    classification_result: Optional[str] = None
    hypotheses_generated: int = 0
    error: Optional[str] = None


def process_stargate_event(event: StarGateEvent, db: Session) -> IntegrationResult:
    """Core processing logic — callable from both HTTP and Kafka handlers."""
    event_id = event.event_id or str(uuid.uuid4())
    payload = event.payload

    bundle_id = f"{payload.get('run_id', 'unknown')}/{payload.get('stage_id', 'unknown')}"
    cluster_id = payload.get("cluster", payload.get("cluster_name", "unknown"))
    stage_id = payload.get("stage_id", "")

    evidence_fields = {
        "outcome": payload.get("outcome", ""),
        "failure_class": payload.get("failure_class", ""),
        "stage_id": stage_id,
        "lab_code": payload.get("lab_code", ""),
        "cluster_name": cluster_id,
        "message": payload.get("message", ""),
    }

    criteria = payload.get("criteria_results", {})
    if isinstance(criteria, dict):
        evidence_fields.update(criteria)
    elif isinstance(criteria, list):
        for c in criteria:
            if isinstance(c, dict) and "name" in c:
                evidence_fields[c["name"]] = c.get("passed", False)

    classification_result = None
    hypotheses_count = 0
    error = None

    try:
        from engine.classification import classify_evidence
        cls_result = classify_evidence({
            "evidence_bundle_id": bundle_id,
            "evidence": evidence_fields,
            "stage": stage_id if stage_id else None,
        }, db)
        classification_result = cls_result.get("overall_result", "unknown")
    except Exception as e:
        logger.warning("Classification failed for %s: %s", bundle_id, e)
        error = f"classification: {e}"

    if payload.get("outcome") in ("fail", "warn", "FAIL", "WARN") or event.event_type in ("evaluation.failed", "evaluation.warned"):
        try:
            from engine.hypothesis import generate_hypotheses
            hyp_result = generate_hypotheses({
                "bundle_id": bundle_id,
                "cluster_id": cluster_id,
                "evidence_fields": evidence_fields,
            }, db)
            hypotheses_count = hyp_result.get("total", 0)
        except Exception as e:
            logger.warning("Hypothesis generation failed for %s: %s", bundle_id, e)
            if error:
                error += f"; hypothesis: {e}"
            else:
                error = f"hypothesis: {e}"

    logger.info(
        "Processed event %s: %s/%s → classification=%s, hypotheses=%d",
        event_id, cluster_id, stage_id, classification_result, hypotheses_count,
    )

    return IntegrationResult(
        event_id=event_id,
        processed=True,
        classification_result=classification_result,
        hypotheses_generated=hypotheses_count,
        error=error,
    )


@router.post("/events", status_code=201, response_model=IntegrationResult)
@limiter.limit("60/minute")
def receive_event(
    request: Request,
    event: StarGateEvent,
    db: Session = Depends(get_db),
):
    """HTTP endpoint for receiving Stargate events."""
    return process_stargate_event(event, db)


@router.post("/events/batch", status_code=201)
@limiter.limit("10/minute")
def receive_events_batch(
    request: Request,
    events: list[StarGateEvent],
    db: Session = Depends(get_db),
):
    """Receive a batch of Stargate events."""
    results = [process_stargate_event(e, db) for e in events]
    return {"processed": len(results), "results": results}
