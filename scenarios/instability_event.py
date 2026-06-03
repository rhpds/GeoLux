"""Geometric instability scenario — tests stability-aware components."""

from __future__ import annotations

from scenarios.base import Scenario
from scenarios import registry


class InstabilityEvent(Scenario):
    name = "instability-event"
    description = "LLM producing unstable outputs. Tests instability gating across all components."
    expected_outcomes = {
        "cluster-health": "pass",
    }
    expected_stability_profile = {
        "mean_score": 0.3,
        "min_score": 0.1,
        "state_distribution": {"unstable_pass": 0.7, "unstable_fail": 0.3},
    }

    def generate_state(self) -> dict:
        return {
            "cluster-health": {
                "cluster_reachable": True,
                "cpu_percent": 70,
                "memory_percent": 75,
                "healthy_node_ratio": 0.9,
            },
        }


registry.register_scenario(InstabilityEvent())
