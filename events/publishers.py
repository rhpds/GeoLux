"""Kafka event publishers for GeoLux components.

Matches Stargate's kafka_publisher.py patterns: lazy producer init,
JSON serialization, configurable acks/retries.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("geolux.kafka")

_producer = None
_KAFKA_BROKERS = os.environ.get("GEOLUX_KAFKA_BROKERS", os.environ.get("STARGATE_KAFKA_BROKERS", ""))


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    if not _KAFKA_BROKERS:
        return None
    try:
        from confluent_kafka import Producer
        _producer = Producer({
            "bootstrap.servers": _KAFKA_BROKERS,
            "acks": "1",
            "retries": 2,
            "request.timeout.ms": 5000,
        })
        logger.info("Kafka producer initialized → %s", _KAFKA_BROKERS)
        return _producer
    except Exception as e:
        logger.warning("Kafka producer init failed: %s", e)
        return None


def _delivery_callback(err, msg):
    if err:
        logger.warning("Kafka delivery failed: %s", err)


def publish_event(
    event_type: str,
    payload: dict,
    key: Optional[str] = None,
) -> bool:
    from events.topics import get_topic_name
    producer = _get_producer()
    if producer is None:
        logger.debug("Kafka not configured — skipping publish for %s", event_type)
        return False
    topic = get_topic_name(event_type)
    message = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    try:
        producer.produce(
            topic=topic,
            key=key or message["event_id"],
            value=json.dumps(message, default=str).encode("utf-8"),
            callback=_delivery_callback,
        )
        producer.poll(0)
        return True
    except Exception as e:
        logger.warning("Failed to publish %s to %s: %s", event_type, topic, e)
        return False


def flush(timeout: float = 5.0):
    producer = _get_producer()
    if producer:
        producer.flush(timeout)


# ── Typed publish helpers ─────────────────────────────────────────────


def publish_hypothesis_generated(hypothesis: dict) -> bool:
    return publish_event("hypothesis.generated", hypothesis, key=hypothesis.get("hypothesis_id"))


def publish_classification_completed(classification: dict) -> bool:
    return publish_event("classification.completed", classification, key=classification.get("classification_id"))


def publish_mpc_action_recommended(action: dict) -> bool:
    return publish_event("mpc.action.recommended", action, key=action.get("cycle_id"))


def publish_routing_decision(decision: dict) -> bool:
    return publish_event("deepfield.routing.decision", decision, key=decision.get("routing_id"))


def publish_intelligence_updated(intelligence: dict) -> bool:
    return publish_event("launchpad.intelligence.updated", intelligence, key=intelligence.get("intelligence_id"))


def publish_audit_event(audit: dict) -> bool:
    return publish_event("audit.event", audit, key=audit.get("event_id"))


def publish_action_executed(action: dict) -> bool:
    return publish_event("action.executed", action, key=action.get("action_id"))
