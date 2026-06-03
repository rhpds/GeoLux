"""Data retention background job.

Deletes records past their configured retention period. Intended to run
on a schedule (e.g. daily cron or Kubernetes CronJob).

Retention policy (from ARCHITECTURE.md):
  - glx_llm_stability_records:  90 days
  - glx_hypotheses:             90 days
  - glx_classifications:        90 days
  - glx_mpc_cycles:             90 days
  - glx_routing_decisions:      90 days
  - glx_nano_obs_records:       90 days
  - glx_launchpad_intelligence: 30 days
  - glx_audit_events:          365 days
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from db.models import (
    AuditEventRecord,
    ClassificationRecord,
    HypothesisRecord,
    LaunchpadIntelligenceRecord,
    LLMStabilityRecord,
    MPCCycleRecord,
    NanoObsRecord,
    RoutingDecisionRecord,
)

logger = logging.getLogger("geolux.retention")

# (model_class, retention_days)
RETENTION_POLICY: list[tuple[type, int]] = [
    (LLMStabilityRecord, 90),
    (HypothesisRecord, 90),
    (ClassificationRecord, 90),
    (MPCCycleRecord, 90),
    (RoutingDecisionRecord, 90),
    (NanoObsRecord, 90),
    (LaunchpadIntelligenceRecord, 30),
    (AuditEventRecord, 365),
]


class RetentionManager:
    """Manages data retention by purging records past their retention window."""

    def __init__(self, db: Session):
        self.db = db

    def run(self) -> dict:
        """Execute retention sweep across all managed tables.

        Returns a summary dict mapping table names to the number of
        rows deleted.
        """
        now = datetime.now(timezone.utc)
        summary: dict[str, int] = {}

        for model_class, retention_days in RETENTION_POLICY:
            table_name = model_class.__tablename__
            cutoff = now - timedelta(days=retention_days)

            try:
                count = (
                    self.db.query(model_class)
                    .filter(model_class.created_at < cutoff)
                    .delete(synchronize_session="fetch")
                )
                summary[table_name] = count

                if count > 0:
                    logger.info(
                        "Retention: deleted %d rows from %s (older than %s)",
                        count,
                        table_name,
                        cutoff.isoformat(),
                    )
                else:
                    logger.debug(
                        "Retention: no expired rows in %s (cutoff %s)",
                        table_name,
                        cutoff.isoformat(),
                    )
            except Exception:
                logger.exception(
                    "Retention: failed to purge %s", table_name
                )
                summary[table_name] = -1

        self.db.commit()

        total = sum(v for v in summary.values() if v > 0)
        logger.info(
            "Retention sweep complete: %d total rows deleted across %d tables",
            total,
            len(summary),
        )

        return summary
