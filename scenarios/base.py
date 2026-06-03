"""Base scenario class for synthetic client.

Extends Stargate's scenario pattern with geometric stability simulation
and expected GeoLux outcomes.
"""

from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session


class Scenario(ABC):
    name: str = "base"
    description: str = ""
    expected_outcomes: dict = {}
    expected_stability_profile: dict = {}
    expected_hypothesis_candidates: list = []
    expected_routing_decisions: list = []

    @abstractmethod
    def generate_state(self) -> dict:
        """Return full cluster state (nodes, pods, namespaces, vms, pools, telemetry)."""

    def generate_evidence(self) -> dict:
        """Derive evidence payloads per stage from generated state."""
        state = self.generate_state()
        evidence = {}
        for stage in self.expected_outcomes:
            evidence[stage] = self._extract_stage_evidence(stage, state)
        return evidence

    def generate_stability_profile(self) -> dict:
        """Return simulated geometric stability profile for this scenario."""
        return self.expected_stability_profile

    def run(self, speed_multiplier: float = 1.0, entropy_level: float = 0.0, db: Optional[Session] = None) -> dict:
        """Execute the scenario and return results."""
        state = self.generate_state()
        evidence = self.generate_evidence()
        stability = self.generate_stability_profile()
        return {
            "scenario": self.name,
            "state": state,
            "evidence": evidence,
            "stability_profile": stability,
            "expected_outcomes": self.expected_outcomes,
        }

    def _extract_stage_evidence(self, stage: str, state: dict) -> dict:
        return state.get(stage, {})
