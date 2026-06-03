"""Unit tests for EventBus and nanoagent pipeline."""

from __future__ import annotations

from events.models import GeoLuxEvent, FilterDecision
from events.nanoagents import (
    DedupeAgent,
    PriorityAgent,
    StabilityGateAgent,
    create_default_pipeline,
)
from events.bus import EventBus, LogConsumer, EventConsumer, create_default_bus


class TestGeoLuxEvent:
    def test_creates_with_defaults(self):
        event = GeoLuxEvent(event_type="test", source_component="unit-test")
        assert event.event_id
        assert event.event_type == "test"
        assert event.filtered is False

    def test_to_dict(self):
        event = GeoLuxEvent(event_type="test", source_component="x", severity="high")
        d = event.to_dict()
        assert d["event_type"] == "test"
        assert d["severity"] == "high"


class TestDedupeAgent:
    def test_first_event_passes(self):
        agent = DedupeAgent(window_seconds=60)
        event = GeoLuxEvent(event_type="eval", source_component="cls", cluster_id="c1")
        result = agent.process(event)
        assert result.filtered is False
        assert result.deduplicated is False

    def test_duplicate_event_filtered(self):
        agent = DedupeAgent(window_seconds=60)
        e1 = GeoLuxEvent(event_type="eval", source_component="cls", cluster_id="c1")
        e2 = GeoLuxEvent(event_type="eval", source_component="cls", cluster_id="c1")
        agent.process(e1)
        result = agent.process(e2)
        assert result.filtered is True
        assert result.deduplicated is True

    def test_different_events_not_deduped(self):
        agent = DedupeAgent(window_seconds=60)
        e1 = GeoLuxEvent(event_type="eval", source_component="cls", cluster_id="c1")
        e2 = GeoLuxEvent(event_type="hyp", source_component="the", cluster_id="c1")
        agent.process(e1)
        result = agent.process(e2)
        assert result.filtered is False

    def test_reset_state(self):
        agent = DedupeAgent()
        agent.process(GeoLuxEvent(event_type="eval", source_component="cls"))
        agent.reset_state()
        result = agent.process(GeoLuxEvent(event_type="eval", source_component="cls"))
        assert result.filtered is False


class TestStabilityGateAgent:
    def test_flags_unstable_events(self):
        agent = StabilityGateAgent()
        event = GeoLuxEvent(geometric_stability_state="unstable_pass")
        result = agent.process(event)
        assert result.metadata.get("stability_flagged") is True
        assert result.priority >= 0.5

    def test_ignores_stable_events(self):
        agent = StabilityGateAgent()
        event = GeoLuxEvent(geometric_stability_state="stable_pass")
        result = agent.process(event)
        assert result.metadata.get("stability_flagged") is None

    def test_skips_events_without_stability(self):
        agent = StabilityGateAgent()
        event = GeoLuxEvent()
        assert agent.should_process(event) is False


class TestPriorityAgent:
    def test_critical_gets_high_priority(self):
        agent = PriorityAgent()
        event = GeoLuxEvent(severity="critical")
        result = agent.process(event)
        assert result.priority == 1.0

    def test_info_gets_zero_priority(self):
        agent = PriorityAgent()
        event = GeoLuxEvent(severity="info")
        result = agent.process(event)
        assert result.priority == 0.0

    def test_low_stability_boosts_priority(self):
        agent = PriorityAgent()
        event = GeoLuxEvent(severity="minor", geometric_stability_score=0.3)
        result = agent.process(event)
        assert result.priority > 0.2


class TestEventBus:
    def test_emit_stores_in_history(self):
        bus = EventBus()
        event = GeoLuxEvent(event_type="test")
        bus.emit(event)
        assert len(bus.history) == 1

    def test_emit_delivers_to_consumers(self):
        received = []

        class TestConsumer(EventConsumer):
            name = "test"
            def deliver(self, event):
                received.append(event)

        bus = EventBus()
        bus.register_consumer(TestConsumer())
        bus.emit(GeoLuxEvent(event_type="test"))
        assert len(received) == 1

    def test_filtered_events_not_delivered_to_default_consumer(self):
        received = []

        class DefaultConsumer(EventConsumer):
            name = "default"
            def deliver(self, event):
                received.append(event)

        bus = EventBus()
        bus.register_consumer(DefaultConsumer())
        event = GeoLuxEvent(event_type="test")
        event.filtered = True
        bus.emit(event)
        assert len(received) == 0

    def test_deduped_events_filtered_by_pipeline(self):
        bus = EventBus()
        received = []

        class Collector(EventConsumer):
            name = "collector"
            def deliver(self, event):
                received.append(event)

        bus.register_consumer(Collector())
        e1 = GeoLuxEvent(event_type="eval", source_component="cls", cluster_id="c1")
        e2 = GeoLuxEvent(event_type="eval", source_component="cls", cluster_id="c1")
        bus.emit(e1)
        bus.emit(e2)
        assert len(received) == 1

    def test_get_recent(self):
        bus = EventBus()
        for i in range(5):
            bus.emit(GeoLuxEvent(event_type=f"type-{i}", source_component="test"))
        assert len(bus.get_recent()) == 5
        assert len(bus.get_recent(event_type="type-0")) == 1

    def test_history_capped(self):
        bus = EventBus(max_history=3)
        for i in range(10):
            bus.emit(GeoLuxEvent(event_type=f"t-{i}", source_component="s"))
        assert len(bus.history) == 3


class TestDefaultPipeline:
    def test_creates_three_agents(self):
        pipeline = create_default_pipeline()
        assert len(pipeline) == 3
        names = [a.name for a in pipeline]
        assert "dedupe" in names
        assert "stability-gate" in names
        assert "priority" in names

    def test_default_bus_has_consumers(self):
        bus = create_default_bus()
        assert len(bus.consumers) == 3
