"""Kafka topic taxonomy for GeoLux platform.

All inter-service communication flows through Kafka. This module defines
the complete topic registry with schemas, producers, and consumers.
"""

from __future__ import annotations


TOPICS = {
    "evidence.collected": {
        "topic": "geolux-evidence-collected",
        "producer": "stargate-collectors",
        "consumers": ["hypothesis-engine", "classification-engine"],
        "description": "Evidence bundles from Stargate collectors",
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
        "partitions": 6,
    },
    "hypothesis.generated": {
        "topic": "geolux-hypothesis-generated",
        "producer": "hypothesis-engine",
        "consumers": ["classification-engine", "stargate-event-bus"],
        "description": "Structured falsifiable hypotheses from THE",
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
        "partitions": 3,
    },
    "classification.completed": {
        "topic": "geolux-classification-completed",
        "producer": "classification-engine",
        "consumers": ["llm-mpc", "deepfield", "stargate-dashboard"],
        "description": "Constraint classification results with evidence chains",
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
        "partitions": 6,
    },
    "mpc.action.recommended": {
        "topic": "geolux-mpc-action-recommended",
        "producer": "llm-mpc",
        "consumers": ["action-execution", "stargate-dashboard"],
        "description": "MPC recommended actions with prediction traces",
        "retention_ms": 30 * 24 * 60 * 60 * 1000,
        "partitions": 3,
    },
    "deepfield.routing.decision": {
        "topic": "geolux-deepfield-routing",
        "producer": "deepfield",
        "consumers": ["inference-serving", "stargate-dashboard"],
        "description": "Workload routing decisions with tier assignments",
        "retention_ms": 30 * 24 * 60 * 60 * 1000,
        "partitions": 3,
    },
    "launchpad.intelligence.updated": {
        "topic": "geolux-launchpad-intelligence",
        "producer": "launchpad",
        "consumers": ["stargate-dashboard", "deepfield-routing-policy"],
        "description": "Provisioning intelligence updates",
        "retention_ms": 30 * 24 * 60 * 60 * 1000,
        "partitions": 1,
    },
    "action.executed": {
        "topic": "geolux-action-executed",
        "producer": "action-execution",
        "consumers": ["audit-trail", "stargate-dashboard"],
        "description": "Executed action results with before/after state",
        "retention_ms": 90 * 24 * 60 * 60 * 1000,
        "partitions": 3,
    },
    "audit.event": {
        "topic": "geolux-audit-events",
        "producer": "all-components",
        "consumers": ["audit-trail-persister", "stargate-dashboard"],
        "description": "Unified audit trail for all GeoLux actions",
        "retention_ms": 365 * 24 * 60 * 60 * 1000,
        "partitions": 6,
    },
    "replay.scenario": {
        "topic": "geolux-replay-scenario",
        "producer": "synthetic-client",
        "consumers": ["evidence-collected-consumers-in-replay-mode"],
        "description": "Synthetic scenario replay events",
        "retention_ms": 7 * 24 * 60 * 60 * 1000,
        "partitions": 1,
    },
}


def get_topic_name(event_type: str) -> str:
    entry = TOPICS.get(event_type)
    if not entry:
        raise ValueError(f"Unknown event type: {event_type}")
    return entry["topic"]


def list_topics() -> list[dict]:
    return [
        {"event_type": k, **v}
        for k, v in TOPICS.items()
    ]
