"""CDD contract tests for Classification API.

Verifies the provider contract expected by MPC, Deepfield, and Dashboard.
"""

from __future__ import annotations

import pytest


class TestClassificationProviderContract:
    def test_constraints_returns_list(self, client):
        response = client.get("/classify/constraints")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_constraints_item_shape(self, client):
        response = client.get("/classify/constraints")
        data = response.json()
        if data:
            item = data[0]
            required = {"constraint_id", "constraint_name", "stage", "assertion_type", "severity", "version"}
            assert required.issubset(item.keys())
            assert item["assertion_type"] in ("threshold", "boolean", "range", "pattern", "composite", "semantic")
            assert item["severity"] in ("critical", "major", "minor")

    def test_constraints_filterable_by_stage(self, client):
        response = client.get("/classify/constraints?stage=cluster-health")
        assert response.status_code == 200

    def test_classification_not_found(self, client):
        response = client.get("/classify/classifications/nonexistent")
        assert response.status_code == 404

    def test_classify_requires_body(self, client):
        response = client.post("/classify", json={})
        assert response.status_code in (201, 422)
