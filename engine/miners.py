"""Data miners for GeoLux — read-only, low-frequency, safe.

Mines historical data from the shared Stargate PostgreSQL database
to populate GeoLux's classification, hypothesis, and intelligence layers.

Safety:
- Read-only queries against shared DB (no writes to Stargate tables)
- Batch processing with pauses (100ms between batches)
- Graceful failure (try/except on every batch)
- One-time backfill with incremental daily refresh
- Skips if already backfilled (checks glx_classifications count)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("geolux.miners")


class EvaluationMiner:
    """Mines Stargate's historical evaluations into GeoLux classification pipeline."""

    def __init__(self, batch_size: int = 200, pause_ms: int = 100):
        self.batch_size = batch_size
        self.pause_ms = pause_ms

    def should_run(self, db: Session) -> bool:
        """Skip if we've already backfilled enough data."""
        from db.models import ClassificationRecord
        count = db.query(ClassificationRecord).count()
        if count > 5000:
            logger.debug("Backfill skipped — already have %d classifications", count)
            return False
        return True

    def run(self, db: Session, days: int = 7, max_batches: int = 50) -> dict:
        """Mine recent Stargate evaluations into GeoLux.

        Reads from Stargate's `evaluations` table (shared DB), processes
        each through the GeoLux classification pipeline.
        """
        if not self.should_run(db):
            return {"skipped": True, "reason": "already backfilled"}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        total_processed = 0
        total_classified = 0
        errors = 0

        try:
            count = db.execute(text(
                "SELECT COUNT(*) FROM evaluations WHERE evaluated_at >= :cutoff AND outcome = 'fail'"
            ), {"cutoff": cutoff}).scalar()
            logger.info("Backfill: %d failure evaluations to process (last %d days)", count, days)
        except Exception as e:
            logger.warning("Backfill count query failed: %s", e)
            return {"error": str(e)}

        for batch_num in range(max_batches):
            try:
                rows = db.execute(text("""
                    SELECT run_id, stage_id, outcome, failure_class, message,
                           lab_code, cluster_name, criteria_results, evaluated_at
                    FROM evaluations
                    WHERE evaluated_at >= :cutoff AND outcome = 'fail'
                    ORDER BY evaluated_at DESC
                    LIMIT :limit OFFSET :offset
                """), {
                    "cutoff": cutoff,
                    "limit": self.batch_size,
                    "offset": batch_num * self.batch_size,
                }).fetchall()

                if not rows:
                    break

                for row in rows:
                    try:
                        self._process_evaluation(row, db)
                        total_classified += 1
                    except Exception:
                        errors += 1

                    total_processed += 1

                db.commit()
                time.sleep(self.pause_ms / 1000.0)

            except Exception as e:
                logger.warning("Backfill batch %d failed: %s", batch_num, e)
                errors += 1
                continue

        logger.info(
            "Backfill complete: processed=%d, classified=%d, errors=%d",
            total_processed, total_classified, errors,
        )

        return {
            "processed": total_processed,
            "classified": total_classified,
            "errors": errors,
        }

    def _process_evaluation(self, row, db: Session):
        """Process a single Stargate evaluation into GeoLux."""
        from api.routers.integration import StarGateEvent, process_stargate_event

        evidence = {}
        if row.criteria_results and isinstance(row.criteria_results, dict):
            evidence = row.criteria_results

        event = StarGateEvent(
            source="stargate-backfill",
            event_type=f"evaluation.{row.outcome}ed" if row.outcome != "warn" else "evaluation.warned",
            payload={
                "run_id": row.run_id or "",
                "stage_id": row.stage_id or "",
                "lab_code": row.lab_code or "",
                "cluster": row.cluster_name or "",
                "outcome": row.outcome or "",
                "failure_class": row.failure_class or "",
                "message": row.message or "",
                "criteria_results": evidence,
            },
        )

        process_stargate_event(event, db)


class LabSummaryMiner:
    """Mines Stargate's materialized lab eval summary for Launchpad intelligence."""

    def run(self, db: Session) -> dict:
        """Read mv_lab_eval_summary and compute Launchpad intelligence."""
        try:
            rows = db.execute(text("""
                SELECT lab_code, cluster_name, total_evals, passed, failed,
                       health_rate, top_failure_class
                FROM mv_lab_eval_summary
                WHERE total_evals > 0
                ORDER BY failed DESC
                LIMIT 500
            """)).fetchall()

            if not rows:
                return {"skipped": True, "reason": "no lab eval data"}

            from engine.launchpad import LaunchpadIntelligence
            intel = LaunchpadIntelligence()

            sessions = []
            for r in rows:
                sessions.append({
                    "demo_id": r.lab_code or "",
                    "partner_id": "",
                    "sa_id": "",
                    "lab_code": r.lab_code or "",
                    "config": r.cluster_name or "",
                    "status": "completed" if r.health_rate and r.health_rate > 50 else "failed",
                    "cost": float(r.total_evals or 0) * 0.01,
                    "hardware_config": "cpu",
                    "started_at": "",
                })

            data = {
                "sessions": sessions,
                "labs": [{"lab_code": r.lab_code} for r in rows],
            }

            signals = intel.compute_demand_signals(data, db)
            costs = intel.compute_cost_attribution(data, db)

            logger.info(
                "Lab summary mined: %d labs, %d sessions, demand=%d signals",
                len(set(r.lab_code for r in rows)),
                len(sessions),
                len(signals.get("most_requested_demos", [])),
            )

            return {
                "labs": len(set(r.lab_code for r in rows)),
                "sessions": len(sessions),
            }

        except Exception as e:
            logger.warning("Lab summary mining failed: %s", e)
            return {"error": str(e)}


class ClusterSummaryMiner:
    """Mines Stargate's cluster summary for MPC objective calibration."""

    def run(self, db: Session) -> dict:
        """Read mv_cluster_summary to calibrate MPC per-cluster objectives."""
        try:
            rows = db.execute(text("""
                SELECT cluster_name, total_evaluations, passed, failed,
                       health_rate, labs_seen, labs_failing
                FROM mv_cluster_summary
                WHERE total_evaluations > 0
                ORDER BY total_evaluations DESC
            """)).fetchall()

            if not rows:
                return {"skipped": True}

            from engine.objectives import set_objective

            for r in rows:
                if r.cluster_name:
                    objective = {
                        "type": "health_target",
                        "target_health_rate": max(float(r.health_rate or 0), 10.0),
                        "baseline_evals": r.total_evaluations,
                        "baseline_pass_rate": float(r.passed or 0) / max(r.total_evaluations, 1) * 100,
                        "labs_monitored": r.labs_seen or 0,
                    }
                    set_objective(r.cluster_name, objective, "backfill-miner", db)

            logger.info("Cluster objectives calibrated: %d clusters", len(rows))
            return {"clusters": len(rows)}

        except Exception as e:
            logger.warning("Cluster summary mining failed: %s", e)
            return {"error": str(e)}
