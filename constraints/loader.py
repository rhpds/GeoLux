"""Constraint definition loader.

Reads YAML constraint definitions from constraints/stages/ and populates
the database. Matches Stargate's rubric_loader.py pattern.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy.orm import Session

from db import repository
from db.models import ConstraintDefinitionRecord

logger = logging.getLogger("geolux.constraints")

_STAGES_DIR = Path(__file__).parent / "stages"


def load_constraint_file(path: Path) -> list[dict]:
    """Load constraints from a single YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "constraints" not in data:
        return []

    stage = data.get("stage", "")
    version = data.get("version", 1)

    constraints = []
    for c in data["constraints"]:
        constraints.append({
            "constraint_id": c["constraint_id"],
            "constraint_name": c["constraint_name"],
            "stage": stage,
            "assertion_type": c["assertion_type"],
            "assertion_definition": c["assertion_definition"],
            "evidence_requirements": c.get("evidence_requirements", []),
            "severity": c.get("severity", "minor"),
            "remediation_class": c.get("remediation_class"),
            "geometric_stability_weight": c.get("geometric_stability_weight", 0.5),
            "version": version,
        })

    return constraints


def load_all_constraints(directory: Optional[Path] = None) -> list[dict]:
    """Load all constraint definitions from the stages directory."""
    stages_dir = directory or _STAGES_DIR
    if not stages_dir.exists():
        logger.warning("Constraints directory not found: %s", stages_dir)
        return []

    all_constraints = []
    for yaml_file in sorted(stages_dir.glob("*.yaml")):
        try:
            constraints = load_constraint_file(yaml_file)
            all_constraints.extend(constraints)
            logger.info("Loaded %d constraints from %s", len(constraints), yaml_file.name)
        except Exception as e:
            logger.warning("Failed to load constraints from %s: %s", yaml_file.name, e)

    return all_constraints


def sync_constraints_to_db(db: Session, directory: Optional[Path] = None) -> dict:
    """Load constraints from YAML and sync to database.

    Creates new constraints, updates existing ones. Does not delete
    constraints that are no longer in YAML (marks deprecated instead).
    """
    constraints = load_all_constraints(directory)

    created = 0
    updated = 0
    unchanged = 0

    existing = {c.constraint_id: c for c in repository.get_constraint_definitions(db)}

    for c in constraints:
        if c["constraint_id"] in existing:
            ex = existing[c["constraint_id"]]
            if ex.version != c["version"]:
                ex.assertion_definition = c["assertion_definition"]
                ex.evidence_requirements = c["evidence_requirements"]
                ex.severity = c["severity"]
                ex.remediation_class = c["remediation_class"]
                ex.geometric_stability_weight = c["geometric_stability_weight"]
                ex.version = c["version"]
                db.flush()
                updated += 1
            else:
                unchanged += 1
        else:
            repository.create_constraint_definition(db, **c)
            created += 1

    db.commit()

    return {
        "total": len(constraints),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
    }


def get_constraints_for_stage(stage: str, db: Session) -> list[ConstraintDefinitionRecord]:
    """Get all active constraints for a specific rubric stage."""
    return repository.get_constraint_definitions(db, stage=stage)
