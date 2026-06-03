"""CDD contract tests for Launchpad Intelligence API.

Verifies the provider contract expected by Dashboard and Deepfield routing policy.
"""

from __future__ import annotations

import pytest


class TestLaunchpadProviderContract:
    def test_intelligence_returns_list(self, client):
        response = client.get("/launchpad/intelligence")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_intelligence_filterable_by_type(self, client):
        response = client.get("/launchpad/intelligence?intelligence_type=demand_signal")
        assert response.status_code == 200

    def test_demand_returns_expected_shape(self, client):
        response = client.get("/launchpad/demand")
        assert response.status_code == 200
        assert "demand_signals" in response.json()

    def test_cost_returns_expected_shape(self, client):
        response = client.get("/launchpad/cost")
        assert response.status_code == 200
        assert "cost_attribution" in response.json()

    def test_utilization_returns_expected_shape(self, client):
        response = client.get("/launchpad/utilization")
        assert response.status_code == 200
        assert "utilization_patterns" in response.json()
