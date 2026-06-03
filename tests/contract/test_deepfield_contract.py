"""CDD contract tests for Deepfield API.

Verifies the provider contract expected by Dashboard and Inference Serving consumers.
"""

from __future__ import annotations

import pytest


class TestDeepfieldProviderContract:
    def test_tiers_returns_expected_shape(self, client):
        response = client.get("/deepfield/tiers")
        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        assert len(data["tiers"]) == 3
        tier_names = {t["name"] for t in data["tiers"]}
        assert tier_names == {"nano", "micro", "macro"}

    def test_tier_item_has_required_fields(self, client):
        response = client.get("/deepfield/tiers")
        for tier in response.json()["tiers"]:
            assert "name" in tier
            assert "substrate" in tier
            assert "agent_type" in tier

    def test_routing_history_returns_list(self, client):
        response = client.get("/deepfield/routing-history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_routing_history_item_shape(self, client):
        response = client.get("/deepfield/routing-history")
        data = response.json()
        if data:
            item = data[0]
            required = {"routing_id", "workload_id", "tier_assignment", "substrate",
                       "confidence_score", "override", "created_at"}
            assert required.issubset(item.keys())
            assert item["tier_assignment"] in ("nano", "micro", "macro")
            assert item["substrate"] in ("cpu", "xeon6", "gaudi")

    def test_route_rejects_override_without_reason(self, client):
        response = client.post("/deepfield/route", json={
            "workload_id": "test",
            "workload_description": {},
            "override_tier": "macro",
        })
        assert response.status_code in (201, 200)
        data = response.json()
        assert "error" in data
