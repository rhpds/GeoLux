"""Summit event data miner.

Mines historical Summit week data as a distinct event context, separate
from day-to-day operations. Summit data is tagged and stored with event
metadata so it can be filtered and analyzed independently.

Summit week: June 2-4, 2026
Pattern: 311K evaluations, 2,198 sandbox sessions, 21 Intel AI demo labs
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.summit")

SUMMIT_START = "2026-06-02"
SUMMIT_END = "2026-06-05"
def _get_demo_labs(db: Session) -> list:
    """Pull demo labs dynamically from Stargate's lab_mappings table."""
    try:
        rows = db.execute(text("SELECT lab_code FROM lab_mappings ORDER BY lab_code")).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []


class SummitMiner:
    """Mines Summit week data into Launchpad intelligence as a distinct event."""

    def run(self, db: Session) -> dict:
        """Extract Summit-specific intelligence from Stargate evaluations."""
        try:
            overview = self._get_overview(db)
            hourly = self._get_hourly_pattern(db)
            demo_performance = self._get_demo_performance(db)
            sandbox_sessions = self._get_sandbox_stats(db)
            failure_profile = self._get_failure_profile(db)
            cluster_load = self._get_cluster_load(db)

            now = datetime.now(timezone.utc)

            repository.create_intelligence_record(
                db,
                intelligence_type="summit_overview",
                data_payload={
                    "event": "Red Hat Summit 2026",
                    "dates": f"{SUMMIT_START} to {SUMMIT_END}",
                    "overview": overview,
                    "hourly_pattern": hourly,
                    "demo_performance": demo_performance,
                    "sandbox_sessions": sandbox_sessions,
                    "failure_profile": failure_profile,
                    "cluster_load": cluster_load,
                },
                time_window_start=datetime.fromisoformat(f"{SUMMIT_START}T00:00:00+00:00"),
                time_window_end=datetime.fromisoformat(f"{SUMMIT_END}T00:00:00+00:00"),
            )

            repository.create_intelligence_record(
                db,
                intelligence_type="demand_signal",
                data_payload={
                    "event": "summit",
                    "most_requested_demos": demo_performance[:10],
                    "highest_failure_configs": failure_profile[:10],
                    "total_sessions": sandbox_sessions.get("total", 0),
                    "returning_partners": [],
                    "new_partners": [],
                },
                time_window_start=datetime.fromisoformat(f"{SUMMIT_START}T00:00:00+00:00"),
                time_window_end=datetime.fromisoformat(f"{SUMMIT_END}T00:00:00+00:00"),
            )

            db.commit()

            logger.info(
                "Summit mined: %d evals, %d sandboxes, %d demos, %d failure classes",
                overview.get("total_evals", 0),
                sandbox_sessions.get("total", 0),
                len(demo_performance),
                len(failure_profile),
            )

            return overview

        except Exception as e:
            logger.warning("Summit mining failed: %s", e)
            return {"error": str(e)}

    def _get_overview(self, db: Session) -> dict:
        r = db.execute(text(f"""
            SELECT COUNT(*) as evals,
                   COUNT(DISTINCT lab_code) as labs,
                   COUNT(DISTINCT cluster_name) as clusters,
                   SUM(CASE WHEN outcome = 'pass' THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN outcome = 'fail' THEN 1 ELSE 0 END) as failed
            FROM evaluations
            WHERE evaluated_at >= '{SUMMIT_START}' AND evaluated_at < '{SUMMIT_END}'
        """)).fetchone()
        return {
            "total_evals": r[0] or 0,
            "total_labs": r[1] or 0,
            "total_clusters": r[2] or 0,
            "passed": r[3] or 0,
            "failed": r[4] or 0,
        }

    def _get_hourly_pattern(self, db: Session) -> list:
        rows = db.execute(text(f"""
            SELECT DATE(evaluated_at) as d,
                   EXTRACT(HOUR FROM evaluated_at) as h,
                   COUNT(*) as c
            FROM evaluations
            WHERE evaluated_at >= '{SUMMIT_START}' AND evaluated_at < '{SUMMIT_END}'
            GROUP BY d, h ORDER BY d, h
        """)).fetchall()
        return [{"date": str(r[0]), "hour": int(r[1]), "count": r[2]} for r in rows]

    def _get_demo_performance(self, db: Session) -> list:
        rows = db.execute(text(f"""
            SELECT lab_code, COUNT(*) as evals,
                   SUM(CASE WHEN outcome = 'pass' THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN outcome = 'fail' THEN 1 ELSE 0 END) as failed,
                   COUNT(DISTINCT cluster_name) as clusters
            FROM evaluations
            WHERE evaluated_at >= '{SUMMIT_START}' AND evaluated_at < '{SUMMIT_END}'
              AND lab_code IN ({','.join(f"'{l}'" for l in _get_demo_labs(db))})
            GROUP BY lab_code ORDER BY evals DESC
        """)).fetchall()
        return [{"demo_id": r[0], "evals": r[1], "passed": r[2], "failed": r[3], "clusters": r[4]} for r in rows]

    def _get_sandbox_stats(self, db: Session) -> dict:
        total = db.execute(text(f"""
            SELECT COUNT(DISTINCT lab_code)
            FROM evaluations
            WHERE lab_code LIKE 'sandbox-%'
              AND evaluated_at >= '{SUMMIT_START}' AND evaluated_at < '{SUMMIT_END}'
        """)).scalar() or 0

        by_day = db.execute(text(f"""
            SELECT DATE(evaluated_at) as d, COUNT(DISTINCT lab_code) as sessions
            FROM evaluations
            WHERE lab_code LIKE 'sandbox-%'
              AND evaluated_at >= '{SUMMIT_START}' AND evaluated_at < '{SUMMIT_END}'
            GROUP BY d ORDER BY d
        """)).fetchall()

        return {
            "total": total,
            "by_day": [{"date": str(r[0]), "sessions": r[1]} for r in by_day],
        }

    def _get_failure_profile(self, db: Session) -> list:
        rows = db.execute(text(f"""
            SELECT failure_class, COUNT(*) as c,
                   COUNT(DISTINCT cluster_name) as clusters,
                   COUNT(DISTINCT lab_code) as labs
            FROM evaluations
            WHERE failure_class IS NOT NULL
              AND evaluated_at >= '{SUMMIT_START}' AND evaluated_at < '{SUMMIT_END}'
            GROUP BY failure_class ORDER BY c DESC LIMIT 15
        """)).fetchall()
        return [{"class": r[0], "count": r[1], "clusters": r[2], "labs": r[3]} for r in rows]

    def _get_cluster_load(self, db: Session) -> list:
        rows = db.execute(text(f"""
            SELECT cluster_name, DATE(evaluated_at) as d,
                   COUNT(*) as evals, COUNT(DISTINCT lab_code) as labs
            FROM evaluations
            WHERE evaluated_at >= '{SUMMIT_START}' AND evaluated_at < '{SUMMIT_END}'
              AND cluster_name IS NOT NULL
            GROUP BY cluster_name, d ORDER BY cluster_name, d
        """)).fetchall()
        return [{"cluster": r[0], "date": str(r[1]), "evals": r[2], "labs": r[3]} for r in rows]
