"""Reclamation miner — classifies AAP destroy failures from Summit receipts.

Reads summit-report.json and creates classifications for each destroy failure
through the standard constraint pipeline. Maps catalog item patterns to
failure classes that match the reclamation-complete constraint stage.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

logger = logging.getLogger("geolux.reclamation")

REPORT_PATH = Path(__file__).parent.parent / "receipts" / "summit-report.json"


def _classify_destroy_type(lab_code: str, catalog_items: list[str]) -> str:
    catalog_str = " ".join(catalog_items).lower()
    lab_lower = (lab_code or "").lower()

    if "tenant" in lab_lower or "tenant" in catalog_str or "slfsrv" in catalog_str:
        return "tenant_destroy_failed"
    if "cnv" in catalog_str and "tenant" not in catalog_str:
        return "cnv_cleanup_failed"
    if "cluster" in catalog_str or "pool" in catalog_str:
        return "cluster_teardown_failed"
    return "destroy_playbook_failed"


class ReclamationMiner:
    """Mines AAP destroy failures from Summit receipts into classifications."""

    def should_run(self, db: Session) -> bool:
        from db.models import ClassificationRecord
        count = db.query(ClassificationRecord).filter(
            ClassificationRecord.evidence_bundle_id.like("aap-destroy/%")
        ).count()
        if count > 0:
            logger.debug("Reclamation backfill skipped — already have %d records", count)
            return False
        return True

    def run(self, db: Session) -> dict:
        if not self.should_run(db):
            return {"skipped": True, "reason": "already backfilled"}

        if not REPORT_PATH.exists():
            logger.info("No summit-report.json found, skipping reclamation mining")
            return {"skipped": True, "reason": "no receipt file"}

        report = json.loads(REPORT_PATH.read_text())
        aap = report.get("aap", {})
        top_failing = aap.get("top_failing_labs", {})

        if not top_failing:
            return {"skipped": True, "reason": "no AAP failure data"}

        from engine.classification import classify_evidence

        classified = 0
        errors = 0

        for lab_code, info in top_failing.items():
            destroy_count = info.get("destroy_failures", 0)
            if destroy_count == 0:
                continue

            catalog_items = info.get("catalog_items", [])
            failure_class = _classify_destroy_type(lab_code, catalog_items)

            evidence = {
                "outcome": "fail",
                "failure_class": failure_class,
                "stage_id": "reclamation-complete",
                "lab_code": lab_code,
                "cluster_name": "",
                "message": f"AAP destroy failed {destroy_count} times during Summit. "
                           f"Catalogs: {', '.join(catalog_items)}. "
                           f"Provision failures: {info.get('provision_failures', 0)}.",
            }

            try:
                classify_evidence({
                    "evidence_bundle_id": f"aap-destroy/{lab_code}",
                    "evidence": evidence,
                    "stage": "reclamation-complete",
                }, db)
                classified += 1
            except Exception as e:
                logger.warning("Reclamation classification failed for %s: %s", lab_code, e)
                errors += 1

        logger.info("Reclamation mining: classified=%d, errors=%d", classified, errors)
        return {"classified": classified, "errors": errors}
