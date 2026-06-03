"""Materialized view refresh functions matching Stargate's pattern.

Aggregate queries for dashboard performance. Called periodically by
background threads.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import (
    LLMStabilityRecord,
    HypothesisRecord,
    ClassificationRecord,
    MPCCycleRecord,
    RoutingDecisionRecord,
)

logger = logging.getLogger("geolux.views")


def refresh_stability_summary(db: Session) -> dict:
    """Compute stability score trends by endpoint."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    try:
        results = db.query(
            LLMStabilityRecord.endpoint,
            func.count(LLMStabilityRecord.id).label("count"),
            func.avg(LLMStabilityRecord.stability_score).label("avg_score"),
        ).filter(
            LLMStabilityRecord.created_at >= cutoff
        ).group_by(LLMStabilityRecord.endpoint).all()

        summary = {r.endpoint: {"count": r.count, "avg_score": float(r.avg_score or 0)} for r in results}
        logger.debug("Stability summary refreshed: %d endpoints", len(summary))
        return summary
    except Exception as e:
        logger.debug("Stability summary refresh failed: %s", e)
        return {}


def refresh_hypothesis_metrics(db: Session) -> dict:
    """Compute hypothesis validation rates and queue depth."""
    try:
        total = db.query(func.count(HypothesisRecord.id)).scalar() or 0
        unresolved = db.query(func.count(HypothesisRecord.id)).filter(
            HypothesisRecord.validation_outcome.is_(None)
        ).scalar() or 0

        return {
            "total": total,
            "queue_depth": unresolved,
            "resolved": total - unresolved,
        }
    except Exception as e:
        logger.debug("Hypothesis metrics refresh failed: %s", e)
        return {}


def refresh_classification_rates(db: Session) -> dict:
    """Compute classification pass/fail/inconclusive rates by stage."""
    try:
        results = db.query(
            ClassificationRecord.result,
            func.count(ClassificationRecord.id).label("count"),
        ).group_by(ClassificationRecord.result).all()

        rates = {r.result.value if hasattr(r.result, 'value') else str(r.result): r.count for r in results}
        logger.debug("Classification rates refreshed: %s", rates)
        return rates
    except Exception as e:
        logger.debug("Classification rates refresh failed: %s", e)
        return {}
