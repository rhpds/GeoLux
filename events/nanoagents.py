"""Nanoagent pipeline for GeoLux event processing.

Matches Stargate's Nanoagent base class + Deepfield's filter/enrich/escalate
outcome pattern. Agents are pure functions with optional module-level state.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from events.models import GeoLuxEvent, FilterDecision

logger = logging.getLogger("geolux.nanoagents")


class Nanoagent:
    """Base class for nanoagent pipeline stages."""

    name: str = "base"

    def should_process(self, event: GeoLuxEvent) -> bool:
        return True

    def process(self, event: GeoLuxEvent) -> GeoLuxEvent:
        return event


class StabilityGateAgent(Nanoagent):
    """Suppress events originating from unstable LLM calls."""

    name = "stability-gate"

    def should_process(self, event: GeoLuxEvent) -> bool:
        return event.geometric_stability_state is not None

    def process(self, event: GeoLuxEvent) -> GeoLuxEvent:
        if event.geometric_stability_state in ("unstable_pass", "unstable_fail"):
            event.priority = max(event.priority, 0.5)
            event.metadata["stability_flagged"] = True
        return event


class DedupeAgent(Nanoagent):
    """Deduplicate events within a configurable time window. Deepfield pattern."""

    name = "dedupe"

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._seen: dict[str, float] = {}

    def _fingerprint(self, event: GeoLuxEvent) -> str:
        return f"{event.source_component}:{event.event_type}:{event.cluster_id or ''}"

    def should_process(self, event: GeoLuxEvent) -> bool:
        return True

    def process(self, event: GeoLuxEvent) -> GeoLuxEvent:
        now = time.time()
        self._cleanup(now)

        fp = self._fingerprint(event)
        if fp in self._seen:
            event.deduplicated = True
            event.filtered = True
            return event

        self._seen[fp] = now
        return event

    def _cleanup(self, now: float):
        stale = [k for k, ts in self._seen.items() if now - ts > self.window_seconds * 10]
        for k in stale:
            del self._seen[k]

    def reset_state(self):
        self._seen.clear()


class PriorityAgent(Nanoagent):
    """Set event priority based on severity and stability."""

    name = "priority"

    SEVERITY_WEIGHTS = {
        "critical": 1.0,
        "high": 0.8,
        "major": 0.6,
        "medium": 0.5,
        "minor": 0.2,
        "low": 0.1,
        "info": 0.0,
    }

    def process(self, event: GeoLuxEvent) -> GeoLuxEvent:
        base = self.SEVERITY_WEIGHTS.get(event.severity, 0.0)

        stability_boost = 0.0
        if event.geometric_stability_score is not None and event.geometric_stability_score < 0.5:
            stability_boost = 0.2

        event.priority = min(1.0, base + stability_boost)
        return event


def create_default_pipeline() -> list[Nanoagent]:
    """Create the default nanoagent pipeline. Order matters."""
    return [
        DedupeAgent(window_seconds=60.0),
        StabilityGateAgent(),
        PriorityAgent(),
    ]
