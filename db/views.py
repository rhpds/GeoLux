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


def refresh_hypothesis_stats(db: Session) -> dict:
    """MV: Hypothesis queue aggregation for /hypotheses/stats."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        total = db.query(func.count(HypothesisRecord.id)).filter(
            HypothesisRecord.created_at >= cutoff
        ).scalar() or 0

        queue_depth = db.query(func.count(HypothesisRecord.id)).filter(
            HypothesisRecord.created_at >= cutoff,
            HypothesisRecord.validation_outcome.is_(None),
        ).scalar() or 0

        validated = db.query(func.count(HypothesisRecord.id)).filter(
            HypothesisRecord.created_at >= cutoff,
            HypothesisRecord.validation_outcome == "validated",
        ).scalar() or 0

        falsified = db.query(func.count(HypothesisRecord.id)).filter(
            HypothesisRecord.created_at >= cutoff,
            HypothesisRecord.validation_outcome == "falsified",
        ).scalar() or 0

        avg_stability = db.query(
            func.avg(HypothesisRecord.geometric_stability_score)
        ).filter(HypothesisRecord.created_at >= cutoff).scalar() or 0

        return {
            "total": total, "queue_depth": queue_depth,
            "validated": validated, "falsified": falsified,
            "avg_stability": float(avg_stability),
        }
    except Exception as e:
        logger.debug("Hypothesis stats refresh failed: %s", e)
        return {}


def refresh_mpc_cycle_summary(db: Session) -> dict:
    """MV: MPC cycle summary by cluster for /mpc/stats."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        results = db.query(
            MPCCycleRecord.cluster_id,
            func.count(MPCCycleRecord.id).label("total_cycles"),
            func.avg(MPCCycleRecord.horizon).label("avg_horizon"),
            func.max(MPCCycleRecord.created_at).label("last_cycle"),
        ).filter(
            MPCCycleRecord.created_at >= cutoff
        ).group_by(MPCCycleRecord.cluster_id).all()

        summary = {
            r.cluster_id: {
                "total_cycles": r.total_cycles,
                "avg_horizon": float(r.avg_horizon or 0),
                "last_cycle": r.last_cycle.isoformat() if r.last_cycle else None,
            }
            for r in results
        }
        logger.debug("MPC cycle summary refreshed: %d clusters", len(summary))
        return summary
    except Exception as e:
        logger.debug("MPC cycle summary refresh failed: %s", e)
        return {}
