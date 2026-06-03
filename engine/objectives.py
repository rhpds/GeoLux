"""MPC objective function management.

Objective functions are per-cluster, versioned, and audited.
Each objective defines what "on-course" looks like for a cluster.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.objectives")

_objectives: dict[str, dict] = {}


def set_objective(
    cluster_id: str,
    objective: dict,
    operator: str,
    db: Session,
) -> dict:
    """Set or update the objective function for a cluster. Versioned and audited."""
    existing = _objectives.get(cluster_id)
    version = (existing["version"] + 1) if existing else 1

    entry = {
        "cluster_id": cluster_id,
        "objective": objective,
        "version": version,
        "set_by": operator,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    _objectives[cluster_id] = entry

    repository.create_audit_event(
        db,
        source_component="llm-mpc",
        event_type="mpc.objective.updated",
        payload_reference=cluster_id,
        operator=operator,
    )
    db.commit()

    logger.info("Objective updated for %s: version %d by %s", cluster_id, version, operator)
    return entry


def get_objective(cluster_id: str) -> Optional[dict]:
    """Get the current objective for a cluster."""
    entry = _objectives.get(cluster_id)
    if entry:
        return entry["objective"]
    return None


def get_objective_history(cluster_id: str) -> dict:
    """Get objective version info for a cluster."""
    entry = _objectives.get(cluster_id)
    if not entry:
        return {"cluster_id": cluster_id, "defined": False}
    return {
        "cluster_id": cluster_id,
        "defined": True,
        "version": entry["version"],
        "set_by": entry["set_by"],
        "set_at": entry["set_at"],
    }
