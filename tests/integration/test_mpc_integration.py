"""Integration tests for LLM-MPC controller."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db.models import ClassificationRecord, ClassificationResult, StabilityState
from db import repository
from engine.mpc import MPCController


@pytest.fixture
def mpc_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _seed_classification_history(db, cluster_id, count=20):
    """Seed enough classification history to pass activation gate."""
    for i in range(count):
        repository.create_classification(
            db,
            evidence_bundle_id=f"{cluster_id}-bundle-{i}",
            constraint_id=f"ch-00{i % 4 + 1}",
            result="pass",
            confidence_score=0.9,
            evidence_chain={"seeded": True},
        )
    db.commit()


def _mock_stable_predict():
    """Mock a stable LLM prediction response."""
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        predictions = json.dumps({
            "predictions": [
                {"step": 1, "predicted_state": {"cpu": 60, "memory": 70}, "confidence": 0.85},
                {"step": 2, "predicted_state": {"cpu": 65, "memory": 72}, "confidence": 0.80},
            ]
        })
        return {
            "content": predictions,
            "success": True,
            "call_id": "mock-call",
            "stability_score": 0.88,
            "stability_state": "stable_pass",
            "stability_method": "token_probability",
            "latency_ms": 100,
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
        }
    return mock_call


def _mock_unstable_predict():
    """Mock an unstable LLM prediction response."""
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        return {
            "content": '{"predictions": []}',
            "success": True,
            "call_id": "mock-call",
            "stability_score": 0.3,
            "stability_state": "unstable_pass",
            "stability_method": "token_probability",
            "latency_ms": 100,
        }
    return mock_call


def _mock_failed_predict():
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        return {
            "content": "",
            "success": False,
            "call_id": "mock-call",
            "stability_score": 0.0,
            "stability_state": "unstable_fail",
            "stability_method": "token_probability",
            "latency_ms": 0,
            "error": "timeout",
        }
    return mock_call


class TestMPCPlanIntegration:
    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_successful_plan_cycle(self, MockClient, mpc_db):
        _seed_classification_history(mpc_db, "cluster-a")
        MockClient.return_value.call = _mock_stable_predict()

        controller = MPCController(default_horizon=2, max_horizon=5, min_history_weeks=0)
        # Override gate to pass
        controller.check_activation_gate = lambda cid, db: True

        result = controller.plan({
            "cluster_id": "cluster-a",
            "current_state": {"cpu": 55, "memory": 65},
            "objective": {"type": "scale", "target": 3},
        }, mpc_db)

        assert "cycle_id" in result
        assert result["cluster_id"] == "cluster-a"
        assert result["horizon"] == 2
        assert result["suspended"] is False
        assert len(result["predictions"]) == 2

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_plan_creates_audit_trail(self, MockClient, mpc_db):
        MockClient.return_value.call = _mock_stable_predict()
        controller = MPCController()
        controller.check_activation_gate = lambda cid, db: True

        controller.plan({
            "cluster_id": "cluster-audit",
            "current_state": {"cpu": 50},
            "objective": {},
        }, mpc_db)

        events = repository.get_audit_events(mpc_db, source_component="llm-mpc")
        assert any(e.event_type == "mpc.cycle.started" for e in events)

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_plan_persists_cycle_to_db(self, MockClient, mpc_db):
        MockClient.return_value.call = _mock_stable_predict()
        controller = MPCController()
        controller.check_activation_gate = lambda cid, db: True

        result = controller.plan({
            "cluster_id": "cluster-persist",
            "current_state": {"cpu": 50},
            "objective": {},
        }, mpc_db)

        cycles = repository.get_mpc_cycles(mpc_db, cluster_id="cluster-persist")
        assert len(cycles) == 1
        assert cycles[0].cycle_id == result["cycle_id"]

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_horizon_shortened_on_instability(self, MockClient, mpc_db):
        MockClient.return_value.call = _mock_unstable_predict()
        controller = MPCController(default_horizon=3, max_horizon=5)
        controller.check_activation_gate = lambda cid, db: True

        result = controller.plan({
            "cluster_id": "cluster-unstable",
            "current_state": {"cpu": 50},
            "objective": {},
            "horizon": 3,
        }, mpc_db)

        assert result["horizon"] <= 3
        assert result["horizon_adjusted"] is True


class TestMPCActivationGate:
    def test_gate_rejects_without_history(self, mpc_db):
        controller = MPCController(min_history_weeks=4)
        result = controller.plan({
            "cluster_id": "new-cluster",
            "current_state": {"cpu": 50},
            "objective": {},
        }, mpc_db)

        assert "error" in result
        assert "insufficient" in result["error"].lower()

    def test_gate_passes_with_enough_history(self, mpc_db):
        _seed_classification_history(mpc_db, "mature-cluster", count=20)
        controller = MPCController(min_history_weeks=0)

        result = controller.check_activation_gate("mature-cluster", mpc_db)
        assert result is True


class TestMPCSuspensionIntegration:
    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_suspension_after_sustained_instability(self, MockClient, mpc_db):
        MockClient.return_value.call = _mock_unstable_predict()
        controller = MPCController()
        controller.check_activation_gate = lambda cid, db: True
        controller._suspension_threshold = 2

        controller.plan({
            "cluster_id": "cluster-suspend",
            "current_state": {"cpu": 50},
            "objective": {},
        }, mpc_db)

        result = controller.plan({
            "cluster_id": "cluster-suspend",
            "current_state": {"cpu": 50},
            "objective": {},
        }, mpc_db)

        assert result["suspended"] is True

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_suspension_creates_audit_event(self, MockClient, mpc_db):
        MockClient.return_value.call = _mock_unstable_predict()
        controller = MPCController()
        controller.check_activation_gate = lambda cid, db: True
        controller._suspension_threshold = 1

        controller.plan({
            "cluster_id": "cluster-audit-suspend",
            "current_state": {"cpu": 50},
            "objective": {},
        }, mpc_db)

        events = repository.get_audit_events(mpc_db, source_component="llm-mpc")
        assert any(e.event_type == "mpc.suspended" for e in events)


class TestMPCAPIEndpoints:
    def test_get_cycles_empty(self, client):
        response = client.get("/mpc/cycles")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_cycle_not_found(self, client):
        response = client.get("/mpc/cycles/nonexistent")
        assert response.status_code == 404
