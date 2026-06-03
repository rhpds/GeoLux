"""End-to-end integration test.

Flows a synthetic scenario through the full pipeline:
  evidence → classification → hypothesis generation → MPC → routing → audit trail.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db import repository
from constraints.loader import sync_constraints_to_db
from engine.classification import classify_evidence
from engine.hypothesis import generate_hypotheses, validate_hypothesis
from engine.mpc import MPCController
from engine.deepfield import DeepfieldRouter
from engine.nanoobs import NanoObsCollector
from engine.launchpad import LaunchpadIntelligence


STAGES_DIR = Path(__file__).parent.parent.parent / "constraints" / "stages"


@pytest.fixture
def e2e_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _mock_stable_llm():
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        if "hypothesis" in endpoint or "hypothesis" in str(messages):
            content = json.dumps([
                {"claim": "CPU is overloaded", "testable_conditions": [{"field": "cpu_percent", "operator": "gt", "value": 90}], "confidence_score": 0.85},
                {"claim": "Memory is healthy", "testable_conditions": [{"field": "memory_percent", "operator": "lt", "value": 80}], "confidence_score": 0.7},
            ])
        elif "predict" in endpoint or "prediction" in endpoint:
            content = json.dumps({"predictions": [{"step": 1, "predicted_state": {"cpu": 70}, "confidence": 0.8}]})
        elif "deepfield" in endpoint or "complexity" in endpoint or "classifier" in endpoint:
            content = json.dumps({"tier": "micro", "reasoning": "moderate complexity", "confidence": 0.85})
        elif "semantic" in endpoint:
            content = json.dumps({"result": "pass", "reasoning": "looks good"})
        else:
            content = json.dumps({"result": "ok"})

        return {
            "content": content,
            "success": True,
            "call_id": "e2e-call",
            "stability_score": 0.88,
            "stability_state": "stable_pass",
            "stability_method": "token_probability",
            "latency_ms": 100,
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
        }
    return mock_call


class TestEndToEndPipeline:
    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    @patch.dict("os.environ", {"GEOLUX_XEON6_URL": "http://xeon6:8080"})
    def test_full_pipeline_healthy_cluster(self, MockClient, e2e_db):
        """Complete pipeline: evidence → classify → hypothesize → MPC → route → audit."""
        MockClient.return_value.call = _mock_stable_llm()

        # Step 1: Load constraints
        sync_constraints_to_db(e2e_db, STAGES_DIR)
        constraints = repository.get_constraint_definitions(e2e_db)
        assert len(constraints) > 0

        # Step 2: Classify evidence (healthy cluster)
        evidence = {
            "cluster_reachable": True,
            "cpu_percent": 50,
            "memory_percent": 60,
            "healthy_node_ratio": 1.0,
        }
        classification = classify_evidence({
            "evidence_bundle_id": "e2e-bundle-1",
            "evidence": evidence,
            "stage": "cluster-health",
        }, e2e_db)

        assert classification["overall_result"] == "pass"
        assert len(classification["results"]) == 4

        # Step 3: Generate hypotheses
        hyp_result = generate_hypotheses({
            "bundle_id": "e2e-bundle-1",
            "evidence_fields": evidence,
        }, e2e_db)

        assert hyp_result["total"] == 2
        assert hyp_result["stability_score"] == 0.88

        # Step 4: Validate hypotheses against evidence
        for h in hyp_result["hypotheses"]:
            outcome = validate_hypothesis(
                {"testable_conditions": h["testable_conditions"]},
                evidence,
            )
            repository.update_hypothesis_validation(e2e_db, h["hypothesis_id"], outcome)

        e2e_db.commit()

        # Step 5: MPC planning
        controller = MPCController(default_horizon=2, max_horizon=5)
        controller.check_activation_gate = lambda cid, db: True

        mpc_result = controller.plan({
            "cluster_id": "e2e-cluster",
            "current_state": evidence,
            "objective": {"type": "scale", "target": 3},
        }, e2e_db)

        assert "cycle_id" in mpc_result
        assert mpc_result["suspended"] is False

        # Step 6: Deepfield routing
        router = DeepfieldRouter()
        route_result = router.route({
            "workload_id": "e2e-workload-1",
            "workload_description": {"task_type": "classify_failure", "reasoning_required": True},
        }, e2e_db)

        assert route_result["tier_assignment"] in ("micro", "macro", "nano")

        # Step 7: NanoObs observation
        collector = NanoObsCollector()
        obs_result = collector.observe("e2e-cluster", "agent-cpu", "cpu_threshold", 50.0, 80.0, e2e_db)
        assert "observation_id" in obs_result

        # Step 8: Verify audit trail is complete
        audit_events = repository.get_audit_events(e2e_db, limit=50)
        event_types = {e.event_type for e in audit_events}
        assert "classification.started" in event_types
        assert "hypothesis.generation.started" in event_types
        assert "mpc.cycle.started" in event_types
        assert "deepfield.routing.started" in event_types

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_full_pipeline_failing_cluster(self, MockClient, e2e_db):
        """Pipeline with unhealthy cluster — classification fails, hypotheses generated."""
        MockClient.return_value.call = _mock_stable_llm()

        sync_constraints_to_db(e2e_db, STAGES_DIR)

        evidence = {
            "cluster_reachable": False,
            "cpu_percent": 95,
            "memory_percent": 92,
            "healthy_node_ratio": 0.3,
        }
        classification = classify_evidence({
            "evidence_bundle_id": "e2e-fail-bundle",
            "evidence": evidence,
            "stage": "cluster-health",
        }, e2e_db)

        assert classification["overall_result"] == "fail"

        hyp_result = generate_hypotheses({
            "bundle_id": "e2e-fail-bundle",
            "evidence_fields": evidence,
        }, e2e_db)
        assert hyp_result["total"] >= 1

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_launchpad_intelligence_computation(self, MockClient, e2e_db):
        """Launchpad computes intelligence from provisioning data."""
        intel = LaunchpadIntelligence()

        data = {
            "sessions": [
                {"demo_id": "ocp", "partner_id": "p1", "sa_id": "s1", "lab_code": "l1",
                 "config": "g8b", "status": "completed", "cost": 100.0,
                 "hardware_config": "gaudi", "started_at": "2026-06-01T10:00:00Z"},
            ],
            "labs": [{"lab_code": "l1"}],
        }

        demand = intel.compute_demand_signals(data, e2e_db)
        assert demand["total_sessions"] == 1
        assert len(demand["most_requested_demos"]) == 1

        costs = intel.compute_cost_attribution(data, e2e_db)
        assert costs["total_cost"] == 100.0

        records = repository.get_intelligence_records(e2e_db)
        assert len(records) >= 2


class TestEndToEndAPIFlow:
    def test_health_returns_mode(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "mode" in response.json()

    def test_all_endpoints_accessible(self, client):
        endpoints = [
            "/health",
            "/mode",
            "/stability/scores",
            "/stability/thresholds",
            "/hypotheses/queue",
            "/classify/constraints",
            "/mpc/cycles",
            "/deepfield/tiers",
            "/deepfield/routing-history",
            "/launchpad/intelligence",
            "/launchpad/demand",
            "/launchpad/cost",
            "/launchpad/utilization",
            "/scenarios/list",
        ]
        for ep in endpoints:
            response = client.get(ep)
            assert response.status_code == 200, f"Failed: GET {ep} returned {response.status_code}"
