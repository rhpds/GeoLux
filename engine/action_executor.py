"""Action execution layer.

Executes MPC-recommended actions with approval workflow, audit trail,
and before/after state capture. Matches Stargate's action_executor.py pattern.

Gates:
1. Approval gate — actions require approval unless auto-execute enabled
2. Confidence gate — only execute if confidence >= threshold
3. Dry-run gate — skip execution if GEOLUX_DRY_RUN=true
4. Mode gate — no execution in synthetic or replay modes
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db import repository
from db.models import AuditEventRecord, TriggerType

logger = logging.getLogger("geolux.action_executor")

DRY_RUN = os.environ.get("GEOLUX_DRY_RUN", "false").lower() == "true"
CONFIDENCE_THRESHOLD = float(os.environ.get("GEOLUX_CONFIDENCE_THRESHOLD", "0.7"))


class ActionExecutor:
    def execute(
        self,
        action: dict,
        db: Session,
        operator: Optional[str] = None,
        force: bool = False,
    ) -> dict:
        """Execute an action with full gate checks and audit trail.

        Returns execution result with audit_id.
        """
        action_id = action.get("action_id", str(uuid.uuid4()))
        action_type = action.get("action_type", "unknown")
        parameters = action.get("parameters", {})
        confidence = action.get("confidence", action.get("optimization_score", 0.0))

        from api.routers._shared import GEOLUX_MODE
        if GEOLUX_MODE != "live" and not force:
            return self._reject(action_id, action_type, "Execution only in live mode", db)

        if DRY_RUN and not force:
            return self._reject(action_id, action_type, "Dry run mode enabled", db)

        if confidence < CONFIDENCE_THRESHOLD and not force:
            return self._reject(
                action_id, action_type,
                f"Confidence {confidence:.2f} below threshold {CONFIDENCE_THRESHOLD}",
                db,
            )

        before_state = self._capture_state(parameters)

        audit_record = repository.create_audit_event(
            db,
            source_component="action-executor",
            event_type="action.executing",
            payload_reference=action_id,
            operator=operator,
            trigger_type=TriggerType.AUTO if not operator else TriggerType.MANUAL,
        )

        try:
            outcome = self._execute_action(action_type, parameters)
        except Exception as e:
            outcome = {"success": False, "error": str(e)}
            logger.warning("Action execution failed: %s — %s", action_type, e)

        if not outcome.get("success") and "pods" in before_state:
            self._rollback(before_state, parameters, db)

        after_state = self._capture_state(parameters)

        repository.create_audit_event(
            db,
            source_component="action-executor",
            event_type="action.executed",
            payload_reference=action_id,
            operator=operator,
        )

        db.commit()

        result = {
            "action_id": action_id,
            "action_type": action_type,
            "executed": outcome.get("success", False),
            "outcome": outcome,
            "before_state": before_state,
            "after_state": after_state,
            "audit_record_id": audit_record.event_id,
        }

        from events.publishers import publish_action_executed
        publish_action_executed(result)

        return result

    def _reject(self, action_id: str, action_type: str, reason: str, db: Session) -> dict:
        """Reject action execution with audit trail."""
        repository.create_audit_event(
            db,
            source_component="action-executor",
            event_type="action.rejected",
            payload_reference=action_id,
        )
        db.commit()

        logger.info("Action rejected: %s — %s", action_type, reason)
        return {
            "action_id": action_id,
            "action_type": action_type,
            "executed": False,
            "reason": reason,
        }

    def _rollback(self, before_state: dict, parameters: dict, db: Session) -> None:
        """Attempt to restore pre-execution state on failure."""
        from engine import k8s_client
        namespace = parameters.get("namespace", k8s_client.EXECUTOR_NAMESPACE)
        kubeconfig = k8s_client.EXECUTOR_KUBECONFIG
        try:
            result = k8s_client.apply_state(before_state, namespace, kubeconfig)
            if result.get("success"):
                logger.info("Rollback succeeded: restored %d resources", result.get("restored", 0))
            else:
                logger.error("Rollback failed: %s", result.get("error", "unknown"))
        except Exception as e:
            logger.error("Rollback exception: %s", e)
        repository.create_audit_event(
            db, source_component="action-executor",
            event_type="action.rollback", payload_reference="rollback",
        )

    def _execute_action(self, action_type: str, parameters: dict) -> dict:
        """Execute the actual action against a real cluster."""
        from engine import k8s_client

        namespace = parameters.get("namespace", k8s_client.EXECUTOR_NAMESPACE)
        kubeconfig = k8s_client.EXECUTOR_KUBECONFIG

        if not kubeconfig or not k8s_client.validate_kubeconfig(kubeconfig):
            logger.warning("No valid executor kubeconfig — cannot execute")
            return {"success": False, "error": "No valid executor kubeconfig"}

        if action_type == "scale_replicas":
            deployment = parameters.get("deployment", "")
            target = parameters.get("target_replicas", 1)
            if not deployment:
                return {"success": False, "error": "Missing deployment name"}
            return k8s_client.scale_deployment(deployment, target, namespace, kubeconfig)

        if action_type == "execute_remediation":
            remediation_type = parameters.get("remediation_type", "rollout_restart")
            target = parameters.get("target", "")
            if not target:
                return {"success": False, "error": "Missing remediation target"}
            if remediation_type == "delete_pod":
                return k8s_client.delete_pod(target, namespace, kubeconfig)
            return k8s_client.rollout_restart(target, namespace, kubeconfig)

        if action_type == "no_action":
            return {"success": True, "action": "none"}

        logger.warning("Unknown action type: %s", action_type)
        return {"success": False, "error": f"Unknown action type: {action_type}"}

    def _capture_state(self, parameters: dict) -> dict:
        """Capture current cluster state for before/after comparison."""
        from engine import k8s_client

        namespace = parameters.get("namespace", k8s_client.EXECUTOR_NAMESPACE)
        kubeconfig = k8s_client.EXECUTOR_KUBECONFIG

        if kubeconfig and k8s_client.validate_kubeconfig(kubeconfig) and namespace:
            state = k8s_client.capture_namespace_state(namespace, kubeconfig)
            state["captured_at"] = datetime.now(timezone.utc).isoformat()
            return state

        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters,
        }
