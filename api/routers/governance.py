"""Governance pipeline endpoint.

Aggregates counts across the full governance lifecycle:
Evidence → Classification → Hypothesis → Approval → Action
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import (
    ClassificationRecord,
    HypothesisRecord,
    MPCCycleRecord,
    AuditEventRecord,
)

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/summit")
def get_summit_intelligence(db: Session = Depends(get_db)):
    """Summit week intelligence — mined as a separate event context."""
    from db.models import LaunchpadIntelligenceRecord
    records = db.query(LaunchpadIntelligenceRecord).filter(
        LaunchpadIntelligenceRecord.intelligence_type == "summit_overview"
    ).order_by(LaunchpadIntelligenceRecord.created_at.desc()).first()

    if not records:
        from engine.summit_miner import SummitMiner
        result = SummitMiner().run(db)
        records = db.query(LaunchpadIntelligenceRecord).filter(
            LaunchpadIntelligenceRecord.intelligence_type == "summit_overview"
        ).order_by(LaunchpadIntelligenceRecord.created_at.desc()).first()

    if not records:
        return {"error": "Summit data not available"}

    return records.data_payload


@router.get("/pipeline")
def get_governance_pipeline(db: Session = Depends(get_db)):
    """Aggregated governance pipeline view — reads both GeoLux and Stargate tables."""

    evidence = _get_evidence_stats(db)
    classifications = _get_classification_stats(db)
    hypotheses = _get_hypothesis_stats(db)
    approvals = _get_approval_stats(db)
    actions = _get_action_stats(db)
    top_failures = _get_top_failure_classes(db)
    clusters = _get_cluster_stats(db)

    return {
        "evidence": evidence,
        "classifications": classifications,
        "hypotheses": hypotheses,
        "approvals": approvals,
        "actions": actions,
        "top_failure_classes": top_failures,
        "clusters": clusters,
    }


def _get_evidence_stats(db: Session) -> dict:
    try:
        total = db.execute(text("SELECT COUNT(*) FROM evaluations")).scalar() or 0
        by_outcome = {}
        rows = db.execute(text("SELECT outcome, COUNT(*) FROM evaluations GROUP BY outcome")).fetchall()
        for r in rows:
            by_outcome[r[0]] = r[1]
        by_cluster = {}
        rows = db.execute(text("SELECT cluster_name, COUNT(*) FROM evaluations WHERE cluster_name IS NOT NULL GROUP BY cluster_name ORDER BY COUNT(*) DESC LIMIT 10")).fetchall()
        for r in rows:
            by_cluster[r[0]] = r[1]
        by_stage = {}
        rows = db.execute(text("SELECT stage_id, COUNT(*) FROM evaluations GROUP BY stage_id ORDER BY COUNT(*) DESC")).fetchall()
        for r in rows:
            by_stage[r[0]] = r[1]
        labs = db.execute(text("SELECT COUNT(DISTINCT lab_code) FROM evaluations WHERE lab_code IS NOT NULL")).scalar() or 0
        return {"total": total, "by_outcome": by_outcome, "by_cluster": by_cluster, "by_stage": by_stage, "labs_monitored": labs}
    except Exception:
        return {"total": 0, "by_outcome": {}, "by_cluster": {}, "by_stage": {}, "labs_monitored": 0}


def _get_classification_stats(db: Session) -> dict:
    total = db.query(func.count(ClassificationRecord.id)).scalar() or 0
    by_result = {}
    rows = db.query(ClassificationRecord.result, func.count(ClassificationRecord.id)).group_by(ClassificationRecord.result).all()
    for r in rows:
        key = r[0].value if hasattr(r[0], 'value') else str(r[0])
        by_result[key] = r[1]
    return {"total": total, **by_result}


def _get_hypothesis_stats(db: Session) -> dict:
    total = db.query(func.count(HypothesisRecord.id)).scalar() or 0
    pending = db.query(func.count(HypothesisRecord.id)).filter(HypothesisRecord.validation_outcome.is_(None)).scalar() or 0
    by_outcome = {}
    rows = db.query(HypothesisRecord.validation_outcome, func.count(HypothesisRecord.id)).group_by(HypothesisRecord.validation_outcome).all()
    for r in rows:
        key = r[0].value if r[0] and hasattr(r[0], 'value') else str(r[0]) if r[0] else "pending"
        by_outcome[key] = r[1]
    return {"total": total, "pending": pending, **by_outcome}


def _get_approval_stats(db: Session) -> dict:
    try:
        total = db.execute(text("SELECT COUNT(*) FROM proposed_classifications")).scalar() or 0
        pending = db.execute(text("SELECT COUNT(*) FROM proposed_classifications WHERE reviewed = false")).scalar() or 0
        approved = db.execute(text("SELECT COUNT(*) FROM proposed_classifications WHERE approved = true")).scalar() or 0
        rejected = db.execute(text("SELECT COUNT(*) FROM proposed_classifications WHERE reviewed = true AND (approved = false OR approved IS NULL)")).scalar() or 0
        top = []
        rows = db.execute(text("SELECT proposed_class, COUNT(*) as c, AVG(confidence) FROM proposed_classifications WHERE reviewed = false GROUP BY proposed_class ORDER BY c DESC LIMIT 10")).fetchall()
        for r in rows:
            top.append({"class": r[0], "count": r[1], "avg_confidence": round(float(r[2] or 0), 2)})
        return {"total": total, "pending": pending, "approved": approved, "rejected": rejected, "top_pending": top}
    except Exception:
        return {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "top_pending": []}


def _get_action_stats(db: Session) -> dict:
    mpc_cycles = db.query(func.count(MPCCycleRecord.id)).scalar() or 0
    suspended = db.query(func.count(MPCCycleRecord.id)).filter(MPCCycleRecord.suspended == True).scalar() or 0
    try:
        remediations = db.execute(text("SELECT COUNT(*) FROM remediations")).scalar() or 0
        pending_actions = db.execute(text("SELECT COUNT(*) FROM pending_actions")).scalar() or 0
    except Exception:
        remediations = 0
        pending_actions = 0
    return {"mpc_cycles": mpc_cycles, "mpc_suspended": suspended, "remediations_applied": remediations, "pending_actions": pending_actions}


def _get_top_failure_classes(db: Session) -> list:
    try:
        rows = db.execute(text("""
            SELECT failure_class, COUNT(*) as c, COUNT(DISTINCT cluster_name) as clusters, COUNT(DISTINCT lab_code) as labs
            FROM evaluations WHERE failure_class IS NOT NULL
            GROUP BY failure_class ORDER BY c DESC LIMIT 10
        """)).fetchall()
        return [{"class": r[0], "count": r[1], "clusters": r[2], "labs": r[3]} for r in rows]
    except Exception:
        return []


def _get_cluster_stats(db: Session) -> list:
    try:
        rows = db.execute(text("SELECT cluster_name, total_evaluations, passed, failed, health_rate, labs_seen, labs_failing FROM mv_cluster_summary ORDER BY total_evaluations DESC")).fetchall()
        return [{
            "name": r[0],
            "evaluations": r[1],
            "passed": r[2],
            "failed": r[3],
            "health_rate": round((r[2] / max(r[1], 1)) * 100, 1),
            "labs_seen": r[5],
            "labs_failing": r[6],
        } for r in rows]
    except Exception:
        return []
