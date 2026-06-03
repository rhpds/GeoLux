"""Node failure scenario — cluster health FAIL."""

from __future__ import annotations

from scenarios.base import Scenario
from scenarios import registry


class NodeFailure(Scenario):
    name = "node-failure"
    description = "Node unreachable, high CPU, low healthy ratio. Cluster health should FAIL."
    expected_outcomes = {
        "cluster-health": "fail",
        "namespace-ready": "pass",
        "deployment-ready": "fail",
    }
    expected_stability_profile = {
        "mean_score": 0.7,
        "min_score": 0.5,
        "state_distribution": {"stable_pass": 0.5, "unstable_pass": 0.5},
    }
    expected_hypothesis_candidates = [
        "Node memory is exhausted",
        "Node is unreachable due to network partition",
    ]

    def generate_state(self) -> dict:
        return {
            "cluster-health": {
                "cluster_reachable": True,
                "cpu_percent": 95,
                "memory_percent": 92,
                "healthy_node_ratio": 0.5,
            },
            "namespace-ready": {
                "namespace_exists": True,
                "namespace_active": True,
                "quota_usage_percent": 80,
            },
            "deployment-ready": {
                "deployment_exists": True,
                "available_replicas": 0,
                "pod_statuses": "CrashLoopBackOff Pending",
            },
        }


registry.register_scenario(NodeFailure())
