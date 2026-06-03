"""Cross-system evidence enrichment for hypothesis generation.

Pulls context from StarGate, DeepField, and Launchpad via stored
events and intelligence records to make hypotheses cross-system aware.
All enrichment is best-effort — failures are logged and skipped.
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.enricher")


class EvidenceEnricher:
    """Enriches evidence bundles with cross-system intelligence."""

    def __init__(self, db: Session):
        self.db = db

    def enrich(self, evidence_bundle: dict) -> dict:
        """Add cross-system context to evidence fields.

        Adds a "cross_system" key to evidence_fields containing data
        from StarGate, DeepField, and Launchpad. Each source is
        independently fetched — if one fails, the others still populate.
        """
        fields = evidence_bundle.get("evidence_fields", {})
        cluster_id = evidence_bundle.get("cluster_id", fields.get("cluster_id"))
        namespace = fields.get("namespace")

        cross_system = {}

        stargate_data = self._get_stargate_context(cluster_id, namespace)
        if stargate_data:
            cross_system["stargate"] = stargate_data

        deepfield_data = self._get_deepfield_context(cluster_id, namespace)
        if deepfield_data:
            cross_system["deepfield"] = deepfield_data

        launchpad_data = self._get_launchpad_context(cluster_id)
        if launchpad_data:
            cross_system["launchpad"] = launchpad_data

        if cross_system:
            fields["cross_system"] = cross_system

        evidence_bundle["evidence_fields"] = fields
        return evidence_bundle

    def _get_stargate_context(self, cluster_id: Optional[str], namespace: Optional[str]) -> Optional[dict]:
        """Pull recent StarGate evaluation context from stored events."""
        try:
            records = repository.get_audit_events(
                self.db,
                source_component="stargate",
                limit=10,
            )
            if not records:
                return None

            # Filter to cluster/namespace if available
            relevant = records
            if cluster_id:
                relevant = [r for r in records if _payload_matches(r, "cluster_id", cluster_id)] or records

            outcomes = [_get_payload_field(r, "outcome") for r in relevant]
            failure_classes = [_get_payload_field(r, "failure_class") for r in relevant if _get_payload_field(r, "failure_class")]

            pass_count = sum(1 for o in outcomes if o == "pass")
            total = len(outcomes)

            return {
                "recent_evaluations": total,
                "failure_classes": list(set(failure_classes)),
                "last_outcome": outcomes[0] if outcomes else None,
                "pass_rate": round(pass_count / total, 2) if total > 0 else None,
            }
        except Exception as e:
            logger.debug("StarGate context fetch failed: %s", e)
            return None

    def _get_deepfield_context(self, cluster_id: Optional[str], namespace: Optional[str]) -> Optional[dict]:
        """Pull DeepField signal intelligence from stored events."""
        try:
            records = repository.get_audit_events(
                self.db,
                source_component="deepfield",
                limit=10,
            )
            if not records:
                return None

            signal_types = [_get_payload_field(r, "signal_type") for r in records if _get_payload_field(r, "signal_type")]
            rca_categories = [_get_payload_field(r, "category") for r in records if _get_payload_field(r, "category")]

            return {
                "recent_events": len(records),
                "signal_types": list(set(signal_types)),
                "rca_categories": list(set(rca_categories)),
            }
        except Exception as e:
            logger.debug("DeepField context fetch failed: %s", e)
            return None

    def _get_launchpad_context(self, cluster_id: Optional[str]) -> Optional[dict]:
        """Pull Launchpad provisioning intelligence from stored records."""
        try:
            records = repository.get_audit_events(
                self.db,
                source_component="launchpad",
                limit=5,
            )
            if not records:
                return None

            return {
                "recent_events": len(records),
                "event_types": list(set(
                    _get_payload_field(r, "event_type") for r in records
                    if _get_payload_field(r, "event_type")
                )),
            }
        except Exception as e:
            logger.debug("Launchpad context fetch failed: %s", e)
            return None


def _payload_matches(record, field: str, value: str) -> bool:
    """Check if an audit record's payload contains a matching field."""
    try:
        payload = record.payload if hasattr(record, "payload") else {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        return str(payload.get(field, "")) == str(value)
    except Exception:
        return False


def _get_payload_field(record, field: str):
    """Extract a field from an audit record's payload."""
    try:
        payload = record.payload if hasattr(record, "payload") else {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        return payload.get(field)
    except Exception:
        return None
