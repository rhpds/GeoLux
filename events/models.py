"""Event and decision models for GeoLux event bus.

Matches Stargate's Event dataclass + Deepfield's FilterDecision pattern.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class GeoLuxEvent:
    """Structured event flowing through the nanoagent pipeline."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_component: str = ""
    cluster_id: Optional[str] = None
    evidence_bundle_id: Optional[str] = None
    outcome: Optional[str] = None
    message: Optional[str] = None
    priority: float = 0.0
    severity: str = "info"
    geometric_stability_score: Optional[float] = None
    geometric_stability_state: Optional[str] = None
    operator: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    filtered: bool = False
    deduplicated: bool = False
    suppressed: bool = False

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "source_component": self.source_component,
            "cluster_id": self.cluster_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "outcome": self.outcome,
            "message": self.message,
            "priority": self.priority,
            "severity": self.severity,
            "geometric_stability_score": self.geometric_stability_score,
            "geometric_stability_state": self.geometric_stability_state,
            "operator": self.operator,
            "metadata": self.metadata,
            "filtered": self.filtered,
            "deduplicated": self.deduplicated,
        }


@dataclass
class FilterDecision:
    """Decision output from a nanoagent. Matches Deepfield's FilterDecision."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    agent_name: str = ""
    outcome: str = "keep"
    reason: str = ""
    evidence: dict = field(default_factory=dict)
