"""Healthy baseline scenario — all stages PASS."""

from __future__ import annotations

from scenarios.base import Scenario
from scenarios import registry


class HealthyBaseline(Scenario):
    name = "healthy-baseline"
    description = "All cluster health indicators nominal. All stages should PASS."
    expected_outcomes = {
        "cluster-health": "pass",
        "namespace-ready": "pass",
        "deployment-ready": "pass",
        "route-ready": "pass",
    }
    expected_stability_profile = {
        "mean_score": 0.9,
        "min_score": 0.85,
        "state_distribution": {"stable_pass": 1.0},
    }

    def generate_state(self) -> dict:
        return {
            "cluster-health": {
                "cluster_reachable": True,
                "cpu_percent": 45,
                "memory_percent": 60,
                "healthy_node_ratio": 1.0,
            },
            "namespace-ready": {
                "namespace_exists": True,
                "namespace_active": True,
                "quota_usage_percent": 30,
            },
            "deployment-ready": {
                "deployment_exists": True,
                "available_replicas": 3,
                "pod_statuses": "Running Running Running",
            },
            "route-ready": {
                "route_exists": True,
                "route_status_code": 200,
                "tls_valid": True,
            },
        }


registry.register_scenario(HealthyBaseline())
