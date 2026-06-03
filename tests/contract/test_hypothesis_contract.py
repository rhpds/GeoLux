"""CDD contract tests for Hypothesis Engine API.

Verifies the provider contract expected by Dashboard and Classification consumers.
"""

from __future__ import annotations

import pytest


class TestHypothesisProviderContract:
    def test_queue_returns_expected_shape(self, client):
        response = client.get("/hypotheses/queue")
        assert response.status_code == 200
        data = response.json()
        assert "hypotheses" in data
        assert "total" in data
        assert isinstance(data["hypotheses"], list)
        assert isinstance(data["total"], int)

    def test_queue_item_has_required_fields(self, client):
        response = client.get("/hypotheses/queue")
        data = response.json()
        if data["hypotheses"]:
            h = data["hypotheses"][0]
            required = {"hypothesis_id", "claim", "testable_conditions",
                       "confidence_score", "geometric_stability_score",
                       "geometric_stability_state", "created_at"}
            assert required.issubset(h.keys())

    def test_get_nonexistent_returns_404(self, client):
        response = client.get("/hypotheses/nonexistent-id")
        assert response.status_code == 404

    def test_validate_rejects_invalid_outcome(self, client):
        response = client.post("/hypotheses/test-id/validate", json={
            "hypothesis_id": "test-id",
            "outcome": "bad_value",
        })
        assert response.status_code == 400

    def test_validate_accepts_valid_outcomes(self, client):
        for outcome in ("validated", "falsified", "inconclusive"):
            response = client.post("/hypotheses/test-id/validate", json={
                "hypothesis_id": "test-id",
                "outcome": outcome,
            })
            assert response.status_code in (200, 404)
