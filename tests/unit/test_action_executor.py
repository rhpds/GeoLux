"""Unit tests for action executor."""

from __future__ import annotations

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db import repository
from engine.action_executor import ActionExecutor


@pytest.fixture
def ae_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestActionExecutor:
    @patch("engine.k8s_client.validate_kubeconfig", return_value=True)
    @patch("engine.k8s_client.EXECUTOR_KUBECONFIG", "/mock/kc")
    @patch("engine.k8s_client.scale_deployment", return_value={"success": True, "replicas": 5, "deployment": "web"})
    @patch("engine.k8s_client.capture_namespace_state", return_value={"pods": [], "deployments": [], "services": []})
    def test_executes_scale_action(self, mock_capture, mock_scale, mock_validate, ae_db):
        import api.routers._shared as _shared
        _shared.GEOLUX_MODE = "live"

        executor = ActionExecutor()
        result = executor.execute(
            {"action_id": "a1", "action_type": "scale_replicas",
             "parameters": {"target_replicas": 5, "deployment": "web", "namespace": "test"},
             "confidence": 0.9},
            ae_db, operator="admin", force=True,
        )
        assert result["executed"] is True
        mock_scale.assert_called_once()
        _shared.GEOLUX_MODE = "live"

    def test_rejects_in_synthetic_mode(self, ae_db):
        import api.routers._shared as _shared
        original = _shared.GEOLUX_MODE
        _shared.GEOLUX_MODE = "synthetic"

        executor = ActionExecutor()
        result = executor.execute(
            {"action_id": "a2", "action_type": "scale_replicas", "confidence": 0.9},
            ae_db,
        )
        assert result["executed"] is False
        assert "live mode" in result["reason"]
        _shared.GEOLUX_MODE = original

    def test_rejects_low_confidence(self, ae_db):
        executor = ActionExecutor()
        result = executor.execute(
            {"action_id": "a3", "action_type": "scale_replicas", "confidence": 0.1},
            ae_db, force=False,
        )
        assert result["executed"] is False
        assert "confidence" in result["reason"].lower() or "Confidence" in result["reason"]

    def test_creates_audit_trail(self, ae_db):
        executor = ActionExecutor()
        executor.execute(
            {"action_id": "a4", "action_type": "no_action", "confidence": 0.9},
            ae_db, operator="test", force=True,
        )
        events = repository.get_audit_events(ae_db, source_component="action-executor")
        assert len(events) >= 1


class TestReplayEngine:
    def test_compare_ground_truth_all_match(self):
        from engine.replay import KafkaReplayEngine
        engine = KafkaReplayEngine()
        result = engine.compare_ground_truth(
            [{"outcome": "pass"}, {"outcome": "fail"}],
            [{"outcome": "pass"}, {"outcome": "fail"}],
        )
        assert result["match"] is True
        assert result["match_rate"] == 1.0

    def test_compare_ground_truth_with_differences(self):
        from engine.replay import KafkaReplayEngine
        engine = KafkaReplayEngine()
        result = engine.compare_ground_truth(
            [{"outcome": "pass"}, {"outcome": "pass"}],
            [{"outcome": "pass"}, {"outcome": "fail"}],
        )
        assert result["match"] is False
        assert len(result["differences"]) == 1

    def test_status_when_not_running(self):
        from engine.replay import KafkaReplayEngine
        engine = KafkaReplayEngine()
        status = engine.get_status()
        assert status["running"] is False


class TestObjectives:
    def test_set_and_get_objective(self, ae_db):
        from engine.objectives import set_objective, get_objective
        set_objective("cluster-x", {"type": "scale", "target": 3}, "admin", ae_db)
        obj = get_objective("cluster-x")
        assert obj["type"] == "scale"

    def test_objective_versioning(self, ae_db):
        from engine.objectives import set_objective, get_objective_history
        set_objective("cluster-v", {"v": 1}, "admin", ae_db)
        set_objective("cluster-v", {"v": 2}, "admin", ae_db)
        history = get_objective_history("cluster-v")
        assert history["version"] == 2

    def test_undefined_objective(self):
        from engine.objectives import get_objective, get_objective_history
        assert get_objective("nonexistent") is None
        h = get_objective_history("nonexistent")
        assert h["defined"] is False
