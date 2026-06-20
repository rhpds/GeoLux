"""CDD contract tests for Stability API.

Verifies that the provider (Stability endpoints) honors the contract
expected by all consumers (Dashboard, Hypothesis Engine, Classification,
MPC, Deepfield).
"""

from __future__ import annotations

import pytest


class TestStabilityProviderContract:
    """Verifies the Stability API provider contract."""

    def test_scores_returns_list(self, client):
        response = client.get("/stability/scores")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_scores_item_shape(self, client):
        response = client.get("/stability/scores")
        data = response.json()
        if data:
            item = data[0]
            required_fields = {"call_id", "endpoint", "model", "stability_score",
                              "stability_method", "stability_threshold", "stability_state", "created_at"}
            assert required_fields.issubset(item.keys())
            assert isinstance(item["stability_score"], (int, float))
            assert 0.0 <= item["stability_score"] <= 1.0
            assert item["stability_state"] in ("stable_pass", "unstable_pass", "stable_fail", "unstable_fail")

    def test_thresholds_shape(self, client):
        response = client.get("/stability/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert "stability_threshold" in data
        assert isinstance(data["stability_threshold"], (int, float))
        assert 0.0 <= data["stability_threshold"] <= 1.0

    def test_threshold_update_requires_auth(self, client):
        response = client.put("/stability/thresholds", json={"threshold": 0.75})
        assert response.status_code == 401

    def test_threshold_update_contract(self, client, admin_headers):
        response = client.put("/stability/thresholds", json={"threshold": 0.75}, headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["stability_threshold"] == 0.75

    def test_threshold_update_rejects_invalid(self, client, admin_headers):
        response = client.put("/stability/thresholds", json={"threshold": 2.0}, headers=admin_headers)
        assert response.status_code == 400
