"""CDD contract tests for LLM-MPC API.

Verifies the provider contract expected by Dashboard and Action Execution consumers.
"""

from __future__ import annotations

import pytest


class TestMPCProviderContract:
    def test_cycles_returns_list(self, client):
        response = client.get("/mpc/cycles")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_cycles_item_shape(self, client):
        response = client.get("/mpc/cycles")
        data = response.json()
        if data:
            item = data[0]
            required = {"cycle_id", "cluster_id", "horizon", "optimization_score",
                       "horizon_adjusted", "suspended", "created_at"}
            assert required.issubset(item.keys())
            assert isinstance(item["horizon"], int)
            assert isinstance(item["suspended"], bool)

    def test_cycles_filterable_by_cluster(self, client):
        response = client.get("/mpc/cycles?cluster_id=test-cluster")
        assert response.status_code == 200

    def test_cycle_not_found(self, client):
        response = client.get("/mpc/cycles/nonexistent")
        assert response.status_code == 404

    def test_plan_requires_cluster_and_state(self, client):
        response = client.post("/mpc/plan", json={
            "cluster_id": "test",
            "current_state": {"cpu": 50},
        })
        assert response.status_code in (201, 422)
