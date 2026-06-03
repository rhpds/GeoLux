"""Integration tests for geometric stability infrastructure.

Tests the full flow: LLM call → stability measurement → DB persistence → API retrieval.
Uses mocked LLM responses with realistic logprobs data.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine, get_db
from db.models import LLMStabilityRecord, StabilityMethod, StabilityState
from db import repository
from api.stability.measure import (
    compute_stability_score,
    determine_stability_state,
    StabilityState as MeasureStabilityState,
)
from api.stability.wrapper import StabilityAwareLLMClient


@pytest.fixture
def integration_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestStabilityAwareLLMClientIntegration:
    """Tests the wrapper calling LLM, measuring stability, and persisting records."""

    def _make_mock_response(self, content="test response", logprobs_data=None):
        """Create a mock LiteLLM response with logprobs."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = content
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50

        if logprobs_data is not None:
            logprobs_mock = MagicMock()
            content_items = []
            for step_probs in logprobs_data:
                token_mock = MagicMock()
                top_logprobs = []
                for lp in step_probs:
                    tlp = MagicMock()
                    tlp.logprob = lp
                    top_logprobs.append(tlp)
                token_mock.top_logprobs = top_logprobs
                content_items.append(token_mock)
            logprobs_mock.content = content_items
            response.choices[0].logprobs = logprobs_mock
        else:
            response.choices[0].logprobs = None

        return response

    @patch("litellm.completion")
    def test_stable_call_persists_stable_pass_record(self, mock_completion, integration_db):
        stable_logprobs = [[-0.05, -4.0, -5.0, -6.0, -7.0]] * 10
        mock_completion.return_value = self._make_mock_response(
            content="cluster is healthy",
            logprobs_data=stable_logprobs,
        )

        client = StabilityAwareLLMClient(
            base_url="http://mock",
            api_key="test",
            model="test-model",
            stability_threshold=0.7,
            stability_method="token_probability",
        )

        result = client.call(
            endpoint="test_classify",
            messages=[{"role": "user", "content": "test"}],
            db=integration_db,
            outcome_correct=True,
        )

        assert result["success"] is True
        assert result["content"] == "cluster is healthy"
        assert result["stability_score"] > 0.0
        assert result["stability_score"] <= 1.0
        assert result["stability_method"] == "token_probability"

        integration_db.commit()
        records = repository.get_stability_records(integration_db, endpoint="test_classify")
        assert len(records) == 1
        assert records[0].endpoint == "test_classify"
        assert records[0].model == "test-model"
        assert records[0].stability_score == result["stability_score"]
        assert records[0].stability_threshold == 0.7

    @patch("litellm.completion")
    def test_unstable_call_persists_unstable_record(self, mock_litellm, integration_db):
        # Top-1 token is uncertain (logprob -3.0) = low stability score
        unstable_logprobs = [[-3.0, -3.5, -4.0, -5.0, -6.0]] * 10
        mock_litellm.return_value = self._make_mock_response(
            content="uncertain result",
            logprobs_data=unstable_logprobs,
        )

        client = StabilityAwareLLMClient(
            base_url="http://mock",
            api_key="test",
            model="test-model",
            stability_threshold=0.5,
            stability_method="token_probability",
        )

        result = client.call(
            endpoint="test_uncertain",
            messages=[{"role": "user", "content": "test"}],
            db=integration_db,
            outcome_correct=False,
        )

        assert result["success"] is True
        assert result["stability_state"] == "unstable_fail"

        integration_db.commit()
        records = repository.get_stability_records(integration_db, endpoint="test_uncertain")
        assert len(records) == 1
        assert records[0].stability_state == StabilityState.UNSTABLE_FAIL

    @patch("litellm.completion")
    def test_llm_failure_returns_unstable_fail(self, mock_litellm, integration_db):
        mock_litellm.side_effect = Exception("Connection refused")

        client = StabilityAwareLLMClient(
            base_url="http://unreachable",
            api_key="test",
            model="test-model",
        )

        result = client.call(
            endpoint="test_fail",
            messages=[{"role": "user", "content": "test"}],
            db=integration_db,
        )

        assert result["success"] is False
        assert result["stability_score"] == 0.0
        assert result["stability_state"] == "unstable_fail"
        assert "Connection refused" in result["error"]

    @patch("litellm.completion")
    def test_no_logprobs_returns_default_score(self, mock_litellm, integration_db):
        mock_litellm.return_value = self._make_mock_response(
            content="no logprobs",
            logprobs_data=None,
        )

        client = StabilityAwareLLMClient(
            base_url="http://mock",
            api_key="test",
            model="test-model",
        )

        result = client.call(
            endpoint="test_no_logprobs",
            messages=[{"role": "user", "content": "test"}],
            db=integration_db,
        )

        assert result["success"] is True
        assert result["stability_score"] == 0.5

    @patch("litellm.completion")
    def test_multiple_calls_persist_multiple_records(self, mock_litellm, integration_db):
        logprobs = [[-0.1, -3.0, -5.0]] * 5
        mock_litellm.return_value = self._make_mock_response(
            content="test", logprobs_data=logprobs,
        )

        client = StabilityAwareLLMClient(
            base_url="http://mock", api_key="test", model="test-model",
        )

        for _ in range(5):
            client.call(
                endpoint="test_multi",
                messages=[{"role": "user", "content": "test"}],
                db=integration_db,
                outcome_correct=True,
            )

        integration_db.commit()
        records = repository.get_stability_records(integration_db, endpoint="test_multi")
        assert len(records) == 5
        for r in records:
            assert r.stability_score > 0.0

    @patch("litellm.completion")
    def test_stability_state_four_quadrants(self, mock_litellm, integration_db):
        """Verify all four stability states can be produced and persisted."""
        # Confident top-1 token = high score
        stable_logprobs = [[-0.05, -5.0, -10.0, -15.0, -18.0]] * 10
        # Uncertain top-1 token = low score
        unstable_logprobs = [[-3.0, -3.5, -4.0, -5.0, -6.0]] * 10

        client = StabilityAwareLLMClient(
            base_url="http://mock", api_key="test", model="test-model",
            stability_threshold=0.5,
        )

        # Stable + correct → stable_pass
        mock_litellm.return_value = self._make_mock_response("ok", stable_logprobs)
        r1 = client.call("ep1", [{"role": "user", "content": "t"}], db=integration_db, outcome_correct=True)

        # Stable + incorrect → stable_fail
        mock_litellm.return_value = self._make_mock_response("bad", stable_logprobs)
        r2 = client.call("ep2", [{"role": "user", "content": "t"}], db=integration_db, outcome_correct=False)

        # Unstable + correct → unstable_pass
        mock_litellm.return_value = self._make_mock_response("ok", unstable_logprobs)
        r3 = client.call("ep3", [{"role": "user", "content": "t"}], db=integration_db, outcome_correct=True)

        # Unstable + incorrect → unstable_fail
        mock_litellm.return_value = self._make_mock_response("bad", unstable_logprobs)
        r4 = client.call("ep4", [{"role": "user", "content": "t"}], db=integration_db, outcome_correct=False)

        assert r1["stability_state"] == "stable_pass"
        assert r2["stability_state"] == "stable_fail"
        assert r3["stability_state"] == "unstable_pass"
        assert r4["stability_state"] == "unstable_fail"


class TestStabilityAPIIntegration:
    """Tests the stability REST API endpoints with test DB."""

    def test_get_scores_empty(self, client):
        response = client.get("/stability/scores")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_thresholds(self, client):
        response = client.get("/stability/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert "stability_threshold" in data
        assert data["stability_threshold"] == 0.7

    def test_update_thresholds_valid(self, client):
        response = client.put("/stability/thresholds", json={"threshold": 0.85})
        assert response.status_code == 200
        assert response.json()["stability_threshold"] == 0.85

    def test_update_thresholds_invalid_above_one(self, client):
        response = client.put("/stability/thresholds", json={"threshold": 1.5})
        assert response.status_code == 400

    def test_update_thresholds_invalid_below_zero(self, client):
        response = client.put("/stability/thresholds", json={"threshold": -0.1})
        assert response.status_code == 400

    def test_get_scores_with_filter(self, client):
        response = client.get("/stability/scores?endpoint=nonexistent")
        assert response.status_code == 200
        assert response.json() == []


class TestStabilityAuditTrail:
    """Verify that stability events create proper audit records."""

    @patch("litellm.completion")
    def test_stability_record_has_raw_signal(self, mock_litellm, integration_db):
        logprobs = [[-0.1, -3.0]] * 5
        mock_litellm.return_value = TestStabilityAwareLLMClientIntegration()._make_mock_response(
            "test", logprobs
        )

        client = StabilityAwareLLMClient(
            base_url="http://mock", api_key="test", model="test-model",
        )
        client.call("audit_test", [{"role": "user", "content": "t"}], db=integration_db, outcome_correct=True)
        integration_db.commit()

        records = repository.get_stability_records(integration_db, endpoint="audit_test")
        assert len(records) == 1
        assert records[0].raw_signal is not None
        assert "logprobs_length" in records[0].raw_signal
        assert "latency_ms" in records[0].raw_signal
