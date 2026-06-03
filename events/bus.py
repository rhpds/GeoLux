"""EventBus for GeoLux — central event processing hub.

Matches Stargate's EventBus pattern: emit → nanoagent pipeline → persist → publish → deliver.
"""

from __future__ import annotations

import logging
from typing import Optional

from events.models import GeoLuxEvent
from events.nanoagents import Nanoagent, create_default_pipeline

logger = logging.getLogger("geolux.eventbus")


class EventConsumer:
    """Base class for event consumers. Matches Stargate's pattern."""

    name: str = "base"

    def should_receive(self, event: GeoLuxEvent) -> bool:
        return not event.filtered

    def deliver(self, event: GeoLuxEvent):
        pass


class LogConsumer(EventConsumer):
    """Logs events with severity formatting."""

    name = "log"
    _SEVERITY_ICONS = {"critical": "[CRIT]", "high": "[HIGH]", "major": "[MAJR]", "medium": "[MED]", "minor": "[MIN]", "info": "[INFO]"}

    def deliver(self, event: GeoLuxEvent):
        icon = self._SEVERITY_ICONS.get(event.severity, "[???]")
        logger.info(
            "%s %s %s — %s (stability=%s, priority=%.2f)",
            icon, event.source_component, event.event_type,
            event.message or event.outcome or "",
            event.geometric_stability_state or "n/a",
            event.priority,
        )


class AuditConsumer(EventConsumer):
    """Persists events to glx_audit_events."""

    name = "audit"

    def should_receive(self, event: GeoLuxEvent) -> bool:
        return True

    def deliver(self, event: GeoLuxEvent):
        try:
            from db.database import get_db
            from db import repository
            from db.models import TriggerType

            db = next(get_db())
            trigger = TriggerType.MANUAL if event.operator else TriggerType.AUTO
            repository.create_audit_event(
                db,
                source_component=event.source_component,
                event_type=event.event_type,
                payload_reference=event.evidence_bundle_id or event.event_id,
                geometric_stability_score=event.geometric_stability_score,
                operator=event.operator,
                trigger_type=trigger,
            )
            db.commit()
            db.close()
        except Exception as e:
            logger.debug("Audit persist failed: %s", e)


class KafkaPublishConsumer(EventConsumer):
    """Publishes events to Kafka topics."""

    name = "kafka"

    def deliver(self, event: GeoLuxEvent):
        try:
            from events.publishers import publish_event
            topic_map = {
                "hypothesis.generation": "hypothesis.generated",
                "classification.": "classification.completed",
                "mpc.cycle": "mpc.action.recommended",
                "deepfield.routing": "deepfield.routing.decision",
                "launchpad.intelligence": "launchpad.intelligence.updated",
                "action.executed": "action.executed",
            }
            for prefix, topic in topic_map.items():
                if event.event_type.startswith(prefix):
                    publish_event(topic, event.to_dict(), key=event.event_id)
                    return
            publish_event("audit.event", event.to_dict(), key=event.event_id)
        except Exception as e:
            logger.debug("Kafka publish failed: %s", e)


class EventBus:
    """Central event processing hub."""

    def __init__(self, max_history: int = 500):
        self.nanoagents: list[Nanoagent] = create_default_pipeline()
        self.consumers: list[EventConsumer] = []
        self.history: list[GeoLuxEvent] = []
        self.max_history = max_history

    def register_consumer(self, consumer: EventConsumer):
        self.consumers.append(consumer)
        logger.info("Registered consumer: %s", consumer.name)

    def emit(self, event: GeoLuxEvent):
        """Process event through pipeline → deliver to consumers."""
        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        for agent in self.nanoagents:
            if agent.should_process(event):
                event = agent.process(event)
                if event.filtered:
                    break

        for consumer in self.consumers:
            try:
                if consumer.should_receive(event):
                    consumer.deliver(event)
            except Exception as e:
                logger.warning("Consumer %s failed: %s", consumer.name, e)

    def get_recent(self, event_type: Optional[str] = None, limit: int = 50) -> list[GeoLuxEvent]:
        events = self.history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]


def create_default_bus() -> EventBus:
    """Create an EventBus with default consumers."""
    bus = EventBus()
    bus.register_consumer(LogConsumer())
    bus.register_consumer(AuditConsumer())
    bus.register_consumer(KafkaPublishConsumer())
    return bus
