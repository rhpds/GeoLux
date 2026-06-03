"""NanoObs — nano agent threshold observation and drift detection.

Observes nano agent execution against current thresholds per cluster.
Detects drift and recommends adaptive threshold adjustments.
Human approval required before production adjustment.

Evidence accumulates per cluster in structured form. THE generates
hypotheses about threshold drift. Constraint classification validates
whether drift is significant enough to warrant adjustment.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.nanoobs")


class NanoObsCollector:
    def observe(
        self,
        cluster_id: str,
        agent_id: str,
        threshold_id: str,
        observed_value: float,
        threshold_value: float,
        db: Session,
    ) -> dict:
        """Record a nano agent observation and check for drift."""
        drift_detected, drift_magnitude = self.detect_drift(
            cluster_id, agent_id, threshold_id, observed_value, threshold_value, db
        )

        adjustment_recommended = False
        adjustment_value = None
        if drift_detected and abs(drift_magnitude) > 0.1:
            adjustment_recommended = True
            adjustment_value = self._compute_adjustment(observed_value, threshold_value, drift_magnitude)

        record = repository.create_nano_obs_record(
            db,
            cluster_id=cluster_id,
            agent_id=agent_id,
            threshold_id=threshold_id,
            observed_value=observed_value,
            threshold_value=threshold_value,
            drift_detected=drift_detected,
            drift_magnitude=drift_magnitude,
            adjustment_recommended=adjustment_recommended,
            adjustment_value=adjustment_value,
        )

        if drift_detected:
            repository.create_audit_event(
                db,
                source_component="nanoobs",
                event_type="nanoobs.drift.detected",
                payload_reference=record.observation_id,
            )
            self._feed_drift_to_hypothesis_engine(
                cluster_id, agent_id, threshold_id,
                observed_value, threshold_value, drift_magnitude, db,
            )

        db.commit()

        return {
            "observation_id": record.observation_id,
            "drift_detected": drift_detected,
            "drift_magnitude": drift_magnitude,
            "adjustment_recommended": adjustment_recommended,
            "adjustment_value": adjustment_value,
        }

    def detect_drift(
        self,
        cluster_id: str,
        agent_id: str,
        threshold_id: str,
        observed_value: float,
        threshold_value: float,
        db: Session,
    ) -> tuple[bool, float]:
        """Detect threshold drift by comparing recent observations.

        Uses statistical analysis of recent values to determine if the
        operating point has shifted significantly from the threshold.
        """
        recent = repository.get_nano_obs_records(db, cluster_id=cluster_id, agent_id=agent_id, limit=20)
        if len(recent) < 5:
            return False, 0.0

        recent_values = [r.observed_value for r in recent[:10]]
        mean = sum(recent_values) / len(recent_values)
        variance = sum((v - mean) ** 2 for v in recent_values) / len(recent_values)
        std_dev = math.sqrt(variance) if variance > 0 else 0.0

        drift_magnitude = (mean - threshold_value) / max(abs(threshold_value), 0.001)

        if abs(drift_magnitude) > 0.15 or std_dev > abs(threshold_value) * 0.3:
            return True, drift_magnitude

        return False, drift_magnitude

    def recommend_adjustment(
        self,
        cluster_id: str,
        agent_id: str,
        threshold_id: str,
        db: Session,
    ) -> Optional[dict]:
        """Generate an adaptive threshold adjustment recommendation.

        Human approval required before any adjustment is applied.
        """
        recent = repository.get_nano_obs_records(db, cluster_id=cluster_id, agent_id=agent_id, limit=50)
        if len(recent) < 10:
            return None

        values = [r.observed_value for r in recent]
        mean = sum(values) / len(values)
        current_threshold = recent[0].threshold_value

        relative_diff = abs(mean - current_threshold) / max(abs(current_threshold), 0.001)
        if relative_diff < 0.1:
            return None

        recommendation = {
            "cluster_id": cluster_id,
            "agent_id": agent_id,
            "threshold_id": threshold_id,
            "current_threshold": current_threshold,
            "recommended_threshold": round(mean, 4),
            "sample_size": len(values),
            "relative_drift": round(relative_diff, 4),
            "requires_human_approval": True,
        }

        repository.create_audit_event(
            db,
            source_component="nanoobs",
            event_type="nanoobs.adjustment.recommended",
            payload_reference=f"{cluster_id}/{agent_id}/{threshold_id}",
        )

        return recommendation

    def approve_adjustment(
        self,
        observation_id: str,
        approved_by: str,
        db: Session,
    ) -> bool:
        """Approve a threshold adjustment. Updates the observation record."""
        from db.models import NanoObsRecord
        record = db.query(NanoObsRecord).filter(
            NanoObsRecord.observation_id == observation_id
        ).first()

        if not record or not record.adjustment_recommended:
            return False

        from datetime import datetime, timezone
        record.adjustment_approved = True
        record.approved_by = approved_by
        record.approved_at = datetime.now(timezone.utc)

        repository.create_audit_event(
            db,
            source_component="nanoobs",
            event_type="nanoobs.adjustment.approved",
            payload_reference=observation_id,
            operator=approved_by,
        )

        db.commit()
        return True

    def _compute_adjustment(self, observed: float, threshold: float, drift: float) -> float:
        """Compute recommended threshold adjustment.

        Uses exponential smoothing — moves threshold halfway toward observed value.
        """
        return round(threshold + (observed - threshold) * 0.5, 4)

    def get_drift_summary(self, cluster_id: str, db: Session) -> dict:
        """Get drift summary for a cluster across all agents."""
        records = repository.get_nano_obs_records(db, cluster_id=cluster_id, limit=100)

        agents = {}
        for r in records:
            if r.agent_id not in agents:
                agents[r.agent_id] = {
                    "agent_id": r.agent_id,
                    "observations": 0,
                    "drifts_detected": 0,
                    "adjustments_recommended": 0,
                    "adjustments_approved": 0,
                }
            agents[r.agent_id]["observations"] += 1
            if r.drift_detected:
                agents[r.agent_id]["drifts_detected"] += 1
            if r.adjustment_recommended:
                agents[r.agent_id]["adjustments_recommended"] += 1
            if r.adjustment_approved:
                agents[r.agent_id]["adjustments_approved"] += 1

        return {
            "cluster_id": cluster_id,
            "total_observations": len(records),
            "agents": list(agents.values()),
        }

    def _feed_drift_to_hypothesis_engine(
        self,
        cluster_id: str,
        agent_id: str,
        threshold_id: str,
        observed_value: float,
        threshold_value: float,
        drift_magnitude: float,
        db: Session,
    ):
        """Feed drift evidence to THE for hypothesis generation about threshold drift."""
        try:
            from engine.hypothesis import generate_hypotheses
            evidence = {
                "bundle_id": f"nanoobs-drift-{cluster_id}-{agent_id}",
                "evidence_fields": {
                    "cluster_id": cluster_id,
                    "agent_id": agent_id,
                    "threshold_id": threshold_id,
                    "observed_value": observed_value,
                    "threshold_value": threshold_value,
                    "drift_magnitude": drift_magnitude,
                    "drift_detected": True,
                },
            }
            generate_hypotheses(evidence, db)
            logger.info(
                "Fed drift to THE: cluster=%s agent=%s drift=%.3f",
                cluster_id, agent_id, drift_magnitude,
            )
        except Exception as e:
            logger.debug("Failed to feed drift to THE: %s", e)
