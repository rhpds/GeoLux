"""Integration tests for Deepfield router and NanoObs."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db import repository
from engine.deepfield import DeepfieldRouter
from engine.nanoobs import NanoObsCollector


@pytest.fixture
def df_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _mock_stable_classify(tier="nano"):
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        return {
            "content": json.dumps({"tier": tier, "reasoning": "test", "confidence": 0.9}),
            "success": True,
            "call_id": "mock",
            "stability_score": 0.85,
            "stability_state": "stable_pass",
            "stability_method": "token_probability",
            "latency_ms": 50,
        }
    return mock_call


def _mock_unstable_classify():
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        return {
            "content": json.dumps({"tier": "nano", "confidence": 0.5}),
            "success": True,
            "call_id": "mock",
            "stability_score": 0.3,
            "stability_state": "unstable_pass",
            "stability_method": "token_probability",
            "latency_ms": 50,
        }
    return mock_call


class TestDeepfieldRouting:
    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_route_nano_workload(self, MockClient, df_db):
        MockClient.return_value.call = _mock_stable_classify("nano")
        router = DeepfieldRouter()
        result = router.route({
            "workload_id": "w-nano",
            "workload_description": {"task_type": "check_pod"},
        }, df_db)

        assert result["tier_assignment"] == "nano"
        assert result["substrate"] == "cpu"
        assert result["confidence_score"] == 0.9
        assert result["override"] is False

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    @patch.dict("os.environ", {"GEOLUX_GAUDI_URL": "http://gaudi:8080"})
    def test_route_macro_workload(self, MockClient, df_db):
        MockClient.return_value.call = _mock_stable_classify("macro")
        router = DeepfieldRouter()
        result = router.route({
            "workload_id": "w-macro",
            "workload_description": {"task_type": "root_cause", "novel": True},
        }, df_db)

        assert result["tier_assignment"] == "macro"
        assert result["substrate"] == "gaudi"

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_route_with_operator_override(self, MockClient, df_db):
        router = DeepfieldRouter()
        result = router.route({
            "workload_id": "w-override",
            "workload_description": {},
            "override_tier": "macro",
            "override_reason": "manual escalation for investigation",
            "override_operator": "admin@redhat.com",
        }, df_db)

        assert result["tier_assignment"] == "macro"
        assert result["override"] is True
        assert result["policy_rule_applied"] == "operator_override"

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    @patch.dict("os.environ", {"GEOLUX_XEON6_URL": "http://xeon6:8080"})
    def test_unstable_classification_escalates_tier(self, MockClient, df_db):
        MockClient.return_value.call = _mock_unstable_classify()
        router = DeepfieldRouter()
        result = router.route({
            "workload_id": "w-unstable",
            "workload_description": {"task_type": "simple_check"},
        }, df_db)

        assert result["tier_assignment"] in ("micro", "macro")
        assert result["confidence_score"] < 0.9

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_route_creates_audit_trail(self, MockClient, df_db):
        MockClient.return_value.call = _mock_stable_classify("nano")
        router = DeepfieldRouter()
        router.route({
            "workload_id": "w-audit",
            "workload_description": {},
        }, df_db)

        events = repository.get_audit_events(df_db, source_component="deepfield")
        assert any(e.event_type == "deepfield.routing.started" for e in events)

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_route_persists_decision(self, MockClient, df_db):
        MockClient.return_value.call = _mock_stable_classify("micro")
        router = DeepfieldRouter()
        result = router.route({
            "workload_id": "w-persist",
            "workload_description": {"reasoning_required": True},
        }, df_db)

        decisions = repository.get_routing_decisions(df_db, workload_id="w-persist")
        assert len(decisions) == 1
        assert decisions[0].routing_id == result["routing_id"]

    @patch.dict("os.environ", {"GEOLUX_GAUDI_URL": "http://gaudi:8080"})
    def test_static_fallback_mode(self, df_db):
        router = DeepfieldRouter()
        router.suspend_adaptive_routing()
        result = router.route({
            "workload_id": "w-static",
            "workload_description": {"novel": True, "reasoning_required": True, "multi_step": True},
        }, df_db)

        assert result["tier_assignment"] == "macro"
        assert result["geometric_stability_score"] is None


class TestNanoObsIntegration:
    def test_observe_no_drift_with_few_records(self, df_db):
        collector = NanoObsCollector()
        result = collector.observe("cluster-a", "agent-1", "cpu_threshold", 75.0, 80.0, df_db)
        assert result["drift_detected"] is False

    def test_observe_detects_drift(self, df_db):
        collector = NanoObsCollector()
        for i in range(10):
            collector.observe("cluster-a", "agent-1", "cpu_threshold", 95.0 + i * 0.1, 80.0, df_db)

        result = collector.observe("cluster-a", "agent-1", "cpu_threshold", 96.0, 80.0, df_db)
        assert result["drift_detected"] is True
        assert result["drift_magnitude"] > 0.1

    def test_observe_recommends_adjustment_on_significant_drift(self, df_db):
        collector = NanoObsCollector()
        for i in range(10):
            collector.observe("cluster-a", "agent-1", "cpu_threshold", 95.0, 80.0, df_db)

        result = collector.observe("cluster-a", "agent-1", "cpu_threshold", 96.0, 80.0, df_db)
        assert result["adjustment_recommended"] is True
        assert result["adjustment_value"] is not None

    def test_recommend_adjustment_requires_minimum_samples(self, df_db):
        collector = NanoObsCollector()
        for i in range(5):
            collector.observe("cluster-b", "agent-2", "mem_threshold", 90.0, 80.0, df_db)

        result = collector.recommend_adjustment("cluster-b", "agent-2", "mem_threshold", df_db)
        assert result is None

    def test_recommend_adjustment_with_sufficient_samples(self, df_db):
        collector = NanoObsCollector()
        for i in range(15):
            collector.observe("cluster-c", "agent-3", "mem_threshold", 90.0, 80.0, df_db)

        result = collector.recommend_adjustment("cluster-c", "agent-3", "mem_threshold", df_db)
        assert result is not None
        assert result["requires_human_approval"] is True
        assert result["recommended_threshold"] > 80.0

    def test_approve_adjustment(self, df_db):
        collector = NanoObsCollector()
        for i in range(10):
            collector.observe("cluster-d", "agent-4", "t1", 95.0, 80.0, df_db)

        obs = collector.observe("cluster-d", "agent-4", "t1", 96.0, 80.0, df_db)
        assert obs["adjustment_recommended"] is True

        approved = collector.approve_adjustment(obs["observation_id"], "admin@test.com", df_db)
        assert approved is True

        events = repository.get_audit_events(df_db, source_component="nanoobs")
        assert any(e.event_type == "nanoobs.adjustment.approved" for e in events)

    def test_drift_creates_audit_event(self, df_db):
        collector = NanoObsCollector()
        for i in range(10):
            collector.observe("cluster-e", "agent-5", "t2", 95.0, 80.0, df_db)

        collector.observe("cluster-e", "agent-5", "t2", 96.0, 80.0, df_db)

        events = repository.get_audit_events(df_db, source_component="nanoobs")
        assert any(e.event_type == "nanoobs.drift.detected" for e in events)

    def test_drift_summary(self, df_db):
        collector = NanoObsCollector()
        for i in range(10):
            collector.observe("cluster-f", "agent-6", "t3", 95.0, 80.0, df_db)

        summary = collector.get_drift_summary("cluster-f", df_db)
        assert summary["cluster_id"] == "cluster-f"
        assert summary["total_observations"] == 10
        assert len(summary["agents"]) == 1


class TestDeepfieldAPIEndpoints:
    def test_get_tiers(self, client):
        response = client.get("/deepfield/tiers")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tiers"]) == 3
        tier_names = {t["name"] for t in data["tiers"]}
        assert tier_names == {"nano", "micro", "macro"}

    def test_get_routing_history_empty(self, client):
        response = client.get("/deepfield/routing-history")
        assert response.status_code == 200
        assert response.json() == []
