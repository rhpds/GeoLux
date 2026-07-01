"""CRUD operations for GeoLux tables.

Follows the same repository pattern as Stargate: functions map between
Pydantic domain models and SQLAlchemy ORM models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db.models import (
    AuditEventRecord,
    ClassificationRecord,
    ConstraintDefinitionRecord,
    HypothesisRecord,
    LaunchpadIntelligenceRecord,
    LLMStabilityRecord,
    MPCCycleRecord,
    NanoObsRecord,
    RoutingDecisionRecord,
    TriggerType,
)


def _generate_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Audit Events ──────────────────────────────────────────────────────


def create_audit_event(
    db: Session,
    source_component: str,
    event_type: str,
    payload_reference: Optional[str] = None,
    geometric_stability_score: Optional[float] = None,
    operator: Optional[str] = None,
    trigger_type: TriggerType = TriggerType.AUTO,
) -> AuditEventRecord:
    record = AuditEventRecord(
        event_id=_generate_id(),
        source_component=source_component,
        event_type=event_type,
        payload_reference=payload_reference,
        geometric_stability_score=geometric_stability_score,
        operator=operator,
        trigger_type=trigger_type,
        created_at=_now(),
    )
    db.add(record)
    db.flush()
    return record


def get_audit_events(
    db: Session,
    source_component: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
) -> list[AuditEventRecord]:
    query = db.query(AuditEventRecord)
    if source_component:
        query = query.filter(AuditEventRecord.source_component == source_component)
    if event_type:
        query = query.filter(AuditEventRecord.event_type == event_type)
    return query.order_by(AuditEventRecord.created_at.desc()).limit(limit).all()


# ── Stability Records ─────────────────────────────────────────────────


def create_stability_record(db: Session, **kwargs) -> LLMStabilityRecord:
    record = LLMStabilityRecord(
        call_id=kwargs.get("call_id", _generate_id()),
        created_at=_now(),
        **{k: v for k, v in kwargs.items() if k != "call_id"},
    )
    db.add(record)
    db.flush()
    return record


def get_stability_records(
    db: Session,
    endpoint: Optional[str] = None,
    limit: int = 100,
) -> list[LLMStabilityRecord]:
    query = db.query(LLMStabilityRecord)
    if endpoint:
        query = query.filter(LLMStabilityRecord.endpoint == endpoint)
    return query.order_by(LLMStabilityRecord.created_at.desc()).limit(limit).all()


# ── Hypotheses ─────────────────────────────────────────────────────────


def create_hypothesis(db: Session, **kwargs) -> HypothesisRecord:
    record = HypothesisRecord(
        hypothesis_id=kwargs.get("hypothesis_id", _generate_id()),
        created_at=_now(),
        **{k: v for k, v in kwargs.items() if k != "hypothesis_id"},
    )
    db.add(record)
    db.flush()
    return record


def get_hypothesis(db: Session, hypothesis_id: str) -> Optional[HypothesisRecord]:
    return db.query(HypothesisRecord).filter(HypothesisRecord.hypothesis_id == hypothesis_id).first()


def get_hypothesis_queue(
    db: Session,
    evidence_bundle_id: Optional[str] = None,
    limit: int = 50,
) -> list[HypothesisRecord]:
    query = db.query(HypothesisRecord).filter(HypothesisRecord.validation_outcome.is_(None))
    if evidence_bundle_id:
        query = query.filter(HypothesisRecord.evidence_bundle_id == evidence_bundle_id)
    return query.order_by(
        HypothesisRecord.created_at.desc(),
        HypothesisRecord.confidence_score.desc(),
    ).limit(limit).all()


def get_hypotheses_for_bundle(
    db: Session,
    evidence_bundle_id: str,
    limit: int = 100,
) -> list[HypothesisRecord]:
    return db.query(HypothesisRecord).filter(
        HypothesisRecord.evidence_bundle_id == evidence_bundle_id
    ).order_by(HypothesisRecord.created_at.desc()).limit(limit).all()


def update_hypothesis_validation(
    db: Session,
    hypothesis_id: str,
    outcome: str,
) -> Optional[HypothesisRecord]:
    record = get_hypothesis(db, hypothesis_id)
    if record:
        record.validation_outcome = outcome
        record.validated_at = _now()
        db.flush()
    return record


# ── Constraint Definitions ─────────────────────────────────────────────


def create_constraint_definition(db: Session, **kwargs) -> ConstraintDefinitionRecord:
    record = ConstraintDefinitionRecord(
        created_at=_now(),
        **kwargs,
    )
    db.add(record)
    db.flush()
    return record


def get_constraint_definitions(
    db: Session,
    stage: Optional[str] = None,
) -> list[ConstraintDefinitionRecord]:
    query = db.query(ConstraintDefinitionRecord).filter(ConstraintDefinitionRecord.deprecated_at.is_(None))
    if stage:
        query = query.filter(ConstraintDefinitionRecord.stage == stage)
    return query.order_by(ConstraintDefinitionRecord.stage, ConstraintDefinitionRecord.constraint_id).all()


# ── Classifications ────────────────────────────────────────────────────


def create_classification(db: Session, **kwargs) -> ClassificationRecord:
    record = ClassificationRecord(
        classification_id=kwargs.get("classification_id", _generate_id()),
        created_at=_now(),
        **{k: v for k, v in kwargs.items() if k != "classification_id"},
    )
    db.add(record)
    db.flush()
    return record


def get_classification(db: Session, classification_id: str) -> Optional[ClassificationRecord]:
    return db.query(ClassificationRecord).filter(
        ClassificationRecord.classification_id == classification_id
    ).first()


# ── MPC Cycles ─────────────────────────────────────────────────────────


def create_mpc_cycle(db: Session, **kwargs) -> MPCCycleRecord:
    record = MPCCycleRecord(
        cycle_id=kwargs.get("cycle_id", _generate_id()),
        created_at=_now(),
        **{k: v for k, v in kwargs.items() if k != "cycle_id"},
    )
    db.add(record)
    db.flush()
    return record


def get_mpc_cycles(
    db: Session,
    cluster_id: Optional[str] = None,
    limit: int = 50,
) -> list[MPCCycleRecord]:
    query = db.query(MPCCycleRecord)
    if cluster_id:
        query = query.filter(MPCCycleRecord.cluster_id == cluster_id)
    return query.order_by(MPCCycleRecord.created_at.desc()).limit(limit).all()


# ── Routing Decisions ──────────────────────────────────────────────────


def create_routing_decision(db: Session, **kwargs) -> RoutingDecisionRecord:
    record = RoutingDecisionRecord(
        routing_id=kwargs.get("routing_id", _generate_id()),
        created_at=_now(),
        **{k: v for k, v in kwargs.items() if k != "routing_id"},
    )
    db.add(record)
    db.flush()
    return record


def get_routing_decisions(
    db: Session,
    workload_id: Optional[str] = None,
    limit: int = 100,
) -> list[RoutingDecisionRecord]:
    query = db.query(RoutingDecisionRecord)
    if workload_id:
        query = query.filter(RoutingDecisionRecord.workload_id == workload_id)
    return query.order_by(RoutingDecisionRecord.created_at.desc()).limit(limit).all()


# ── NanoObs Records ────────────────────────────────────────────────────


def create_nano_obs_record(db: Session, **kwargs) -> NanoObsRecord:
    record = NanoObsRecord(
        observation_id=kwargs.get("observation_id", _generate_id()),
        created_at=_now(),
        **{k: v for k, v in kwargs.items() if k != "observation_id"},
    )
    db.add(record)
    db.flush()
    return record


def get_nano_obs_records(
    db: Session,
    cluster_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 100,
) -> list[NanoObsRecord]:
    query = db.query(NanoObsRecord)
    if cluster_id:
        query = query.filter(NanoObsRecord.cluster_id == cluster_id)
    if agent_id:
        query = query.filter(NanoObsRecord.agent_id == agent_id)
    return query.order_by(NanoObsRecord.created_at.desc()).limit(limit).all()


# ── Launchpad Intelligence ─────────────────────────────────────────────


def create_intelligence_record(db: Session, **kwargs) -> LaunchpadIntelligenceRecord:
    record = LaunchpadIntelligenceRecord(
        intelligence_id=kwargs.get("intelligence_id", _generate_id()),
        created_at=_now(),
        **{k: v for k, v in kwargs.items() if k not in ("intelligence_id", "created_at")},
    )
    db.add(record)
    db.flush()
    return record


def get_intelligence_records(
    db: Session,
    intelligence_type: Optional[str] = None,
    limit: int = 50,
) -> list[LaunchpadIntelligenceRecord]:
    query = db.query(LaunchpadIntelligenceRecord)
    if intelligence_type:
        query = query.filter(LaunchpadIntelligenceRecord.intelligence_type == intelligence_type)
    return query.order_by(LaunchpadIntelligenceRecord.created_at.desc()).limit(limit).all()
