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
        """Process a single Stargate evaluation — classification only, no hypotheses."""
        from engine.classification import classify_evidence

        from api.routers.integration import FAILURE_TO_STAGE, _map_stage

        evidence_fields = {
            "outcome": row.outcome or "",
            "failure_class": row.failure_class or "",
            "stage_id": row.stage_id or "",
            "lab_code": row.lab_code or "",
            "cluster_name": row.cluster_name or "",
            "message": row.message or "",
        }

        bundle_id = f"{row.run_id or 'unknown'}/{row.stage_id or 'unknown'}"
        mapped_stage = _map_stage(row.stage_id or "", row.failure_class or "")

        classify_evidence({
            "evidence_bundle_id": bundle_id,
            "evidence": evidence_fields,
            "stage": mapped_stage,
        }, db)


class LabSummaryMiner:
    """Mines Stargate's lab data for real demo lab intelligence."""

    def run(self, db: Session) -> dict:
        """Extract demo lab performance — only user-facing labs, not infrastructure."""
        try:
            from db import repository

            mapped_labs = db.execute(text("SELECT lab_code FROM lab_mappings")).fetchall()
            mapped_names = [r[0] for r in mapped_labs]

            demo_labs = db.execute(text("""
                SELECT lab_code, COUNT(*) as evals,
                       SUM(CASE WHEN outcome = 'pass' THEN 1 ELSE 0 END) as passed,
                       SUM(CASE WHEN outcome = 'fail' THEN 1 ELSE 0 END) as failed,
                       COUNT(DISTINCT cluster_name) as clusters
                FROM evaluations
                WHERE (lab_code LIKE 'user-demo-tenant-%%'
                       OR lab_code LIKE 'ocp4-%%'
                       OR lab_code LIKE 'intel-%%'
                       OR lab_code LIKE 'sandbox-%%')
                GROUP BY lab_code
                HAVING COUNT(*) > 10
                ORDER BY COUNT(*) DESC
                LIMIT 50
            """)).fetchall()

            sandbox_count = db.execute(text(
                "SELECT COUNT(DISTINCT lab_code) FROM evaluations WHERE lab_code LIKE 'sandbox-%%'"
            )).scalar() or 0

            now = datetime.now(timezone.utc)
            repository.create_intelligence_record(
                db,
                intelligence_type="demo_lab_performance",
                data_payload={
                    "mapped_labs": mapped_names,
                    "mapped_lab_count": len(mapped_names),
                    "sandbox_sessions": sandbox_count,
                    "demo_labs": [
                        {"lab": r[0], "evals": r[1], "passed": r[2], "failed": r[3], "clusters": r[4]}
                        for r in demo_labs
                    ],
                },
                time_window_start=now,
                time_window_end=now,
            )
            db.commit()

            logger.info("Lab summary: %d mapped labs, %d sandbox sessions, %d active demos",
                        len(mapped_names), sandbox_count, len(demo_labs))
            return {"mapped": len(mapped_names), "sandboxes": sandbox_count, "demos": len(demo_labs)}

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
