"""Kafka consumer framework for GeoLux.

Reads from topics and dispatches to registered handler functions.
Matches Stargate's event consumer pattern.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Callable, Optional

logger = logging.getLogger("geolux.kafka.consumer")

_KAFKA_BROKERS = os.environ.get("GEOLUX_KAFKA_BROKERS", "")


class KafkaConsumerManager:
    """Manages Kafka consumers for all GeoLux topics."""

    def __init__(self, group_id: str = "geolux-consumers"):
        self.group_id = group_id
        self._handlers: dict[str, list[Callable]] = {}
        self._consumers: list = []
        self._running = False
        self._threads: list[threading.Thread] = []

    def register_handler(self, topic: str, handler: Callable[[dict], None]):
        """Register a handler function for a Kafka topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        logger.info("Registered handler for topic %s: %s", topic, handler.__name__)

    def start(self):
        """Start consuming from all registered topics."""
        if not _KAFKA_BROKERS:
            logger.info("Kafka not configured — consumers not started")
            return

        if self._running:
            return

        self._running = True

        for topic, handlers in self._handlers.items():
            t = threading.Thread(
                target=self._consume_topic,
                args=(topic, handlers),
                daemon=True,
                name=f"kafka-consumer-{topic}",
            )
            self._threads.append(t)
            t.start()
            logger.info("Started consumer thread for %s", topic)

    def stop(self):
        """Stop all consumer threads."""
        self._running = False
        for consumer in self._consumers:
            try:
                consumer.close()
            except Exception:
                pass
        self._consumers.clear()
        logger.info("Kafka consumers stopped")

    def _consume_topic(self, topic: str, handlers: list[Callable]):
        """Consume messages from a single topic and dispatch to handlers."""
        try:
            from confluent_kafka import Consumer, KafkaError

            consumer = Consumer({
                "bootstrap.servers": _KAFKA_BROKERS,
                "group.id": self.group_id,
                "auto.offset.reset": "latest",
                "enable.auto.commit": True,
                "session.timeout.ms": 30000,
            })
            consumer.subscribe([topic])
            self._consumers.append(consumer)

            while self._running:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.warning("Consumer error on %s: %s", topic, msg.error())
                    continue

                try:
                    value = json.loads(msg.value().decode("utf-8"))
                    for handler in handlers:
                        try:
                            handler(value)
                        except Exception as e:
                            logger.warning("Handler error on %s: %s", topic, e)
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON on %s: %s", topic, e)

        except ImportError:
            logger.warning("confluent-kafka not installed — consumer for %s not started", topic)
        except Exception as e:
            logger.warning("Consumer for %s failed: %s", topic, e)


def create_default_consumer_manager() -> KafkaConsumerManager:
    """Create a consumer manager with default handlers for all GeoLux topics."""
    from events.topics import get_topic_name

    manager = KafkaConsumerManager()

    manager.register_handler(
        get_topic_name("evidence.collected"),
        _handle_evidence_collected,
    )
    manager.register_handler(
        get_topic_name("hypothesis.generated"),
        _handle_hypothesis_generated,
    )
    manager.register_handler(
        get_topic_name("classification.completed"),
        _handle_classification_completed,
    )
    manager.register_handler(
        get_topic_name("mpc.action.recommended"),
        _handle_mpc_action_recommended,
    )
    manager.register_handler(
        get_topic_name("tarsy.investigation.completed"),
        _handle_tarsy_investigation_completed,
    )

    return manager


def _handle_evidence_collected(message: dict):
    """Process incoming evidence bundles — trigger classification and hypothesis generation."""
    payload = message.get("payload", {})
    logger.info("Evidence collected: bundle_id=%s", payload.get("bundle_id", "unknown"))


def _handle_hypothesis_generated(message: dict):
    """Process new hypotheses — feed to classification engine."""
    payload = message.get("payload", {})
    logger.info("Hypothesis generated: %s", payload.get("hypothesis_id", "unknown"))


def _handle_classification_completed(message: dict):
    """Process classification results — feed to MPC and Deepfield."""
    payload = message.get("payload", {})
    logger.info("Classification completed: %s", payload.get("evidence_bundle_id", "unknown"))


def _handle_mpc_action_recommended(message: dict):
    """Process MPC action recommendations — feed to action execution layer."""
    payload = message.get("payload", {})
    logger.info("MPC action recommended: %s", payload.get("cycle_id", "unknown"))


def _handle_tarsy_investigation_completed(message: dict):
    """Process TARSy investigation results through the governance pipeline.

    Routes completed investigations through the hypothesis engine for
    stability-gated validation before any recommended actions can proceed.
    """
    payload = message.get("payload", {})
    trace_id = message.get("trace_id", payload.get("trace_id", ""))
    source = payload.get("source", "unknown")
    status = payload.get("status", "")

    if status != "completed":
        logger.info("TARSy investigation %s: status=%s, skipping governance",
                     payload.get("tarsy_session_id", ""), status)
        return

    logger.info("TARSy investigation completed: session=%s source=%s trace=%s",
                 payload.get("tarsy_session_id"), source, trace_id)

    # Build evidence bundle for hypothesis engine
    evidence_bundle = {
        "bundle_id": f"tarsy-{payload.get('tarsy_session_id', '')}",
        "source": "tarsy",
        "trace_id": trace_id,
        "evidence_fields": {
            "root_causes": payload.get("root_causes", []),
            "confidence": _extract_max_confidence(payload.get("root_causes", [])),
            "recommended_actions": payload.get("recommended_actions", []),
            "executive_summary": payload.get("executive_summary", ""),
            "investigation_gaps": payload.get("investigation_gaps", []),
            "originating_source": source,
            "originator_id": payload.get("originator_id", ""),
            "score": payload.get("score"),
        },
    }

    # Feed to hypothesis engine — stability gate applies automatically
    try:
        from db.database import get_db
        from engine.hypothesis import generate_hypotheses
        db = next(get_db())
        result = generate_hypotheses(evidence_bundle, db)
        logger.info("Hypotheses generated from TARSy: %d (gated=%s)",
                     result.get("total", 0), result.get("gated", False))
        db.close()
    except Exception as e:
        logger.warning("Hypothesis generation from TARSy result failed: %s", e)

    # Publish governance audit event
    try:
        from events.publishers import publish_audit_event
        publish_audit_event({
            "source_component": "tarsy-governance",
            "event_type": "tarsy.investigation.governed",
            "tarsy_session_id": payload.get("tarsy_session_id"),
            "trace_id": trace_id,
            "source": source,
            "originator_id": payload.get("originator_id", ""),
            "actions_count": len(payload.get("recommended_actions", [])),
            "root_causes_count": len(payload.get("root_causes", [])),
        })
    except Exception as e:
        logger.debug("Audit event publish failed (non-critical): %s", e)


def _extract_max_confidence(root_causes: list) -> float:
    confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
    if not root_causes:
        return 0.0
    scores = [confidence_map.get(rc.get("confidence", "low"), 0.3) for rc in root_causes]
    return max(scores)


def _handle_deepfield_finding(message: dict):
    """Process DeepField findings for cross-system hypothesis generation."""
    payload = message.get("payload", message)
    logger.info(
        "DeepField finding: %s severity=%s",
        payload.get("summary", payload.get("title", "unknown"))[:60],
        payload.get("severity", "?"),
    )
    try:
        from api.routers.integration import StarGateEvent, process_stargate_event
        from db.database import get_db
        db = next(get_db())
        event = StarGateEvent(
            source="deepfield-kafka",
            event_type="deepfield.finding",
            payload={
                "run_id": payload.get("id", payload.get("finding_id", "")),
                "stage_id": "cross-system",
                "cluster": payload.get("cluster_id", payload.get("cluster", "")),
                "outcome": "fail" if payload.get("severity") in ("high", "critical") else "warn",
                "failure_class": payload.get("category", payload.get("signal_type", "")),
                "message": payload.get("summary", payload.get("title", "")),
            },
        )
        process_stargate_event(event, db)
        db.close()
    except Exception as e:
        logger.debug("DeepField finding handler error: %s", e)


def _handle_deepfield_incident(message: dict):
    """Process DeepField incidents — high-severity cross-system events."""
    payload = message.get("payload", message)
    logger.info("DeepField incident: %s", payload.get("summary", "unknown")[:60])


def _handle_launchpad_lifecycle(message: dict):
    """Process Launchpad lifecycle events — session creation/completion/failure."""
    payload = message.get("payload", message)
    event_type = payload.get("event_type", payload.get("type", "unknown"))
    logger.info("Launchpad lifecycle: %s session=%s", event_type, payload.get("session_id", "?")[:20])
