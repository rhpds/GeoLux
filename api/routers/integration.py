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


import time as _time
_mpc_last_planned: dict[str, float] = {}
_MPC_COOLDOWN = 3600  # 1 hour between MPC cycles per cluster


def _should_plan_mpc(cluster_id: str) -> bool:
    """Rate limit MPC planning to once per 5 minutes per cluster."""
    now = _time.time()
    last = _mpc_last_planned.get(cluster_id, 0)
    if now - last < _MPC_COOLDOWN:
        return False
    _mpc_last_planned[cluster_id] = now
    return True


FAILURE_TO_STAGE = {
    "deprecated_api": "cluster-health",
    "readiness_probe_failed": "route-ready",
    "scheduling_failed": "deployment-ready",
    "claim_misbound": "namespace-ready",
    "datasource_unrecognized": "storage-clone-ready",
    "pvc_binding_failed": "namespace-ready",
    "pod_pending": "deployment-ready",
    "pods_crashlooping": "deployment-ready",
    "sync_failed": "cluster-health",
    "hpa_metric_failure": "cluster-health",
    "invalid_configuration": "cluster-health",
    "backoff_limit_exceeded": "run-created",
    "volume_attach_failed": "storage-clone-ready",
    "volume_mount_failed": "storage-clone-ready",
    "vm_migration_backoff": "vm-runtime-ready",
    "image_pull_backoff": "deployment-ready",
    "tenant_destroy_failed": "reclamation-complete",
    "cnv_cleanup_failed": "reclamation-complete",
    "cluster_teardown_failed": "reclamation-complete",
    "destroy_playbook_failed": "reclamation-complete",
}


def _map_stage(stage_id: str, failure_class: str) -> str:
    """Map a failure class to the appropriate constraint stage."""
    if stage_id and stage_id != "cluster-health":
        return stage_id
    if failure_class:
        return FAILURE_TO_STAGE.get(failure_class, stage_id or "cluster-health")
    return stage_id or "cluster-health"


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

    mapped_stage = _map_stage(stage_id, payload.get("failure_class", ""))

    try:
        from engine.classification import classify_evidence
        from api.routers._shared import invalidate_constraint_cache
        invalidate_constraint_cache()
        cls_result = classify_evidence({
            "evidence_bundle_id": bundle_id,
            "evidence": evidence_fields,
            "stage": mapped_stage if mapped_stage else None,
        }, db)
        classification_result = cls_result.get("overall_result", "unknown")
    except Exception as e:
        logger.warning("Classification failed for %s: %s", bundle_id, e)
        error = f"classification: {e}"

    is_failure = payload.get("outcome") in ("fail", "warn", "FAIL", "WARN") or event.event_type in ("evaluation.failed", "evaluation.warned")

    if is_failure:
        from api.routers._shared import HYPOTHESIS_ENABLED
        if not HYPOTHESIS_ENABLED:
            logger.debug("Hypothesis generation disabled — skipping")
        else:
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

    if is_failure:
        try:
            from engine.deepfield import DeepfieldRouter
            failure_class = payload.get("failure_class", "")
            novel = failure_class in ("", "unknown")
            reasoning = failure_class in ("pods_crashlooping", "readiness_probe_failed", "vm_migration_backoff", "invalid_configuration")
            router_engine = DeepfieldRouter()
            router_engine.route({
                "workload_id": bundle_id,
                "workload_description": {
                    "task_type": f"classify_{failure_class}" if failure_class else "unknown_failure",
                    "reasoning_required": reasoning,
                    "novel": novel,
                    "multi_step": reasoning and novel,
                    "context_length": len(str(evidence_fields)),
                },
            }, db)
        except Exception:
            pass

        from api.routers._shared import MPC_ENABLED
        if MPC_ENABLED and _should_plan_mpc(cluster_id):
            try:
                from engine.mpc import MPCController
                from engine.objectives import get_objective
                controller = MPCController()
                if controller.check_activation_gate(cluster_id, db):
                    controller.plan({
                        "cluster_id": cluster_id,
                        "current_state": evidence_fields,
                        "objective": get_objective(cluster_id) or {"type": "health_target"},
                    }, db)
            except Exception:
                pass

    try:
        _auto_validate_hypotheses(evidence_fields, db)
    except Exception:
        pass

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


def _auto_validate_hypotheses(evidence: dict, db: Session):
    """Auto-validate pending hypotheses against new evidence.

    When a new event arrives, check pending hypotheses for the same cluster.
    If the hypothesis conditions match the evidence, validate or falsify it.
    """
    from engine.hypothesis import validate_hypothesis
    from db import repository

    cluster = evidence.get("cluster_name", "")
    if not cluster:
        return

    pending = repository.get_hypothesis_queue(db, limit=20)
    for h in pending:
        if not h.evidence_snapshot:
            continue
        snapshot_cluster = h.evidence_snapshot.get("cluster_name", "")
        if snapshot_cluster != cluster:
            continue

        outcome = validate_hypothesis(
            {"testable_conditions": h.testable_conditions or []},
            evidence,
        )

        if outcome != "inconclusive":
            repository.update_hypothesis_validation(db, h.hypothesis_id, outcome)

    db.commit()
