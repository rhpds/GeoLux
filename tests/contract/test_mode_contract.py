"""CDD contract tests for Mode and Health API.

Verifies the contract expected by all frontend consumers.
"""

from __future__ import annotations

import pytest


class TestHealthContract:
    def test_health_shape(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "mode" in data
        assert data["mode"] in ("live", "synthetic", "replay")
        assert data["service"] == "geolux"


class TestModeContract:
    def test_get_mode_shape(self, client):
        response = client.get("/mode")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "valid_modes" in data
        assert set(data["valid_modes"]) == {"live", "synthetic", "replay"}

    def test_set_mode_returns_updated(self, client):
        response = client.put("/mode", json={"mode": "synthetic"})
        assert response.status_code == 200
        assert response.json()["mode"] == "synthetic"
        client.put("/mode", json={"mode": "live"})

    def test_set_invalid_mode_returns_400(self, client):
        response = client.put("/mode", json={"mode": "nonexistent"})
        assert response.status_code == 400


class TestScenarioContract:
    def test_list_scenarios_shape(self, client):
        response = client.get("/scenarios/list")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert isinstance(data["scenarios"], list)
        if data["scenarios"]:
            s = data["scenarios"][0]
            assert "name" in s
            assert "description" in s
