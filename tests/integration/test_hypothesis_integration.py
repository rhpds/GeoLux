"""Integration tests for Hypothesis Engine (THE).

Tests the full flow: evidence bundle → LLM generation → stability measurement →
DB persistence → API retrieval → validation → Kafka publication.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db.models import HypothesisRecord, StabilityState, ValidationOutcome
from db import repository
from engine.hypothesis import (
    generate_hypotheses,
    validate_hypothesis,
    check_all_falsified,
    _parse_hypotheses,
)


@pytest.fixture
def hyp_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _mock_stable_llm_response(hypotheses_json: list[dict]):
    """Create a mock that simulates a stable LLM call returning hypotheses."""
    content = json.dumps(hypotheses_json)

    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        return {
            "content": content,
            "success": True,
            "call_id": "test-call-id",
            "stability_score": 0.85,
            "stability_state": "stable_pass",
            "stability_method": "token_probability",
            "latency_ms": 100,
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
        }

    return mock_call


def _mock_unstable_llm_response():
    """Create a mock that simulates an unstable LLM call."""
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        return {
            "content": "[]",
            "success": True,
            "call_id": "test-call-id",
            "stability_score": 0.3,
            "stability_state": "unstable_pass",
            "stability_method": "token_probability",
            "latency_ms": 100,
        }
    return mock_call


def _mock_failed_llm():
    """Create a mock that simulates LLM unavailability."""
    def mock_call(endpoint, messages, max_tokens=500, temperature=0.1, db=None, outcome_correct=None):
        return {
            "content": "",
            "success": False,
            "call_id": "test-call-id",
            "stability_score": 0.0,
            "stability_state": "unstable_fail",
            "stability_method": "token_probability",
            "latency_ms": 0,
            "error": "Connection refused",
        }
    return mock_call


class TestGenerateHypotheses:
    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_generates_and_persists_hypotheses(self, MockClient, hyp_db):
        test_hypotheses = [
            {
                "claim": "Node memory is exhausted",
                "testable_conditions": [
                    {"field": "memory_percent", "operator": "gt", "value": 90}
                ],
                "confidence_score": 0.8,
            },
            {
                "claim": "Pod is in CrashLoopBackOff",
                "testable_conditions": [
                    {"field": "pod_status", "operator": "eq", "value": "CrashLoopBackOff"}
                ],
                "confidence_score": 0.7,
            },
        ]
        MockClient.return_value.call = _mock_stable_llm_response(test_hypotheses)

        bundle = {
            "bundle_id": "test-bundle-1",
            "cluster_id": "cluster-a",
            "evidence_fields": {"memory_percent": 95, "pod_status": "CrashLoopBackOff"},
        }
        result = generate_hypotheses(bundle, hyp_db)

        assert result["total"] == 2
        assert len(result["hypotheses"]) == 2
        assert result["evidence_bundle_id"] == "test-bundle-1"
        assert result["stability_score"] == 0.85
        assert "audit_record_id" in result

        records = repository.get_hypothesis_queue(hyp_db, evidence_bundle_id="test-bundle-1")
        assert len(records) == 2

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_hypotheses_ranked_by_stability(self, MockClient, hyp_db):
        test_hypotheses = [
            {"claim": "low confidence", "testable_conditions": [], "confidence_score": 0.3},
            {"claim": "high confidence", "testable_conditions": [], "confidence_score": 0.9},
        ]
        MockClient.return_value.call = _mock_stable_llm_response(test_hypotheses)

        result = generate_hypotheses({"bundle_id": "b1"}, hyp_db)

        assert result["hypotheses"][0]["confidence_score"] >= result["hypotheses"][1]["confidence_score"]

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_instability_gate_blocks_generation(self, MockClient, hyp_db):
        MockClient.return_value.call = _mock_unstable_llm_response()

        result = generate_hypotheses(
            {"bundle_id": "gated-bundle"},
            hyp_db,
            stability_threshold=0.7,
        )

        assert result["gated"] is True
        assert result["total"] == 0
        assert "instability" in result["reason"].lower()

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_llm_unavailable_returns_stale(self, MockClient, hyp_db):
        MockClient.return_value.call = _mock_failed_llm()

        result = generate_hypotheses({"bundle_id": "unavailable-bundle"}, hyp_db)

        assert result.get("stale") is True
        assert "unavailable" in result["reason"].lower()

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_audit_trail_created(self, MockClient, hyp_db):
        MockClient.return_value.call = _mock_stable_llm_response([
            {"claim": "test", "testable_conditions": [], "confidence_score": 0.5}
        ])

        result = generate_hypotheses({"bundle_id": "audit-test"}, hyp_db)

        audit_events = repository.get_audit_events(
            hyp_db, source_component="hypothesis-engine"
        )
        assert len(audit_events) >= 1
        assert any(e.event_type == "hypothesis.generation.started" for e in audit_events)

    @patch("api.stability.wrapper.StabilityAwareLLMClient")
    def test_evidence_snapshot_stored(self, MockClient, hyp_db):
        evidence = {"cpu": 85, "memory": 70, "pods_running": 5}
        MockClient.return_value.call = _mock_stable_llm_response([
            {"claim": "cpu high", "testable_conditions": [{"field": "cpu", "operator": "gt", "value": 80}], "confidence_score": 0.8}
        ])

        result = generate_hypotheses(
            {"bundle_id": "snap-test", "evidence_fields": evidence},
            hyp_db,
        )

        record = repository.get_hypothesis(hyp_db, result["hypotheses"][0]["hypothesis_id"])
        assert record.evidence_snapshot is not None
        assert record.evidence_snapshot.get("cpu") == 85


class TestHypothesisValidationFlow:
    def test_validate_then_update_db(self, hyp_db):
        record = repository.create_hypothesis(
            hyp_db,
            evidence_bundle_id="flow-test",
            claim="CPU is above 90%",
            testable_conditions=[{"field": "cpu", "operator": "gt", "value": 90}],
            confidence_score=0.8,
            geometric_stability_score=0.85,
            geometric_stability_method="token_probability",
            geometric_stability_state="stable_pass",
        )
        hyp_db.commit()

        outcome = validate_hypothesis(
            {"testable_conditions": record.testable_conditions},
            {"cpu": 95},
        )
        assert outcome == "validated"

        repository.update_hypothesis_validation(hyp_db, record.hypothesis_id, outcome)
        hyp_db.commit()

        updated = repository.get_hypothesis(hyp_db, record.hypothesis_id)
        assert updated.validation_outcome.value == "validated"
        assert updated.validated_at is not None

    def test_falsification_updates_db(self, hyp_db):
        record = repository.create_hypothesis(
            hyp_db,
            evidence_bundle_id="falsify-test",
            claim="Memory is low",
            testable_conditions=[{"field": "memory", "operator": "lt", "value": 30}],
            confidence_score=0.6,
            geometric_stability_score=0.9,
            geometric_stability_method="token_probability",
            geometric_stability_state="stable_pass",
        )
        hyp_db.commit()

        outcome = validate_hypothesis(
            {"testable_conditions": record.testable_conditions},
            {"memory": 75},
        )
        assert outcome == "falsified"

        repository.update_hypothesis_validation(hyp_db, record.hypothesis_id, outcome)
        hyp_db.commit()

        updated = repository.get_hypothesis(hyp_db, record.hypothesis_id)
        assert updated.validation_outcome.value == "falsified"


class TestCheckAllFalsified:
    def test_returns_false_when_no_hypotheses(self, hyp_db):
        assert check_all_falsified("nonexistent-bundle", hyp_db) is False

    def test_returns_false_when_unresolved(self, hyp_db):
        repository.create_hypothesis(
            hyp_db,
            evidence_bundle_id="partial-test",
            claim="test",
            testable_conditions=[],
            confidence_score=0.5,
            geometric_stability_score=0.8,
            geometric_stability_method="token_probability",
            geometric_stability_state="stable_pass",
        )
        hyp_db.commit()

        assert check_all_falsified("partial-test", hyp_db) is False

    def test_returns_true_when_all_falsified(self, hyp_db):
        for i in range(3):
            r = repository.create_hypothesis(
                hyp_db,
                evidence_bundle_id="all-false",
                claim=f"hyp {i}",
                testable_conditions=[],
                confidence_score=0.5,
                geometric_stability_score=0.8,
                geometric_stability_method="token_probability",
                geometric_stability_state="stable_pass",
            )
            repository.update_hypothesis_validation(hyp_db, r.hypothesis_id, "falsified")
        hyp_db.commit()

        assert check_all_falsified("all-false", hyp_db) is True

        audit_events = repository.get_audit_events(
            hyp_db, source_component="hypothesis-engine", event_type="hypothesis.all_falsified"
        )
        assert len(audit_events) == 1


class TestHypothesisAPIEndpoints:
    def test_get_queue_empty(self, client):
        response = client.get("/hypotheses/queue")
        assert response.status_code == 200
        data = response.json()
        assert data["hypotheses"] == []
        assert data["total"] == 0

    def test_get_hypothesis_not_found(self, client):
        response = client.get("/hypotheses/nonexistent-id")
        assert response.status_code == 404

    def test_validate_invalid_outcome(self, client):
        response = client.post(
            "/hypotheses/some-id/validate",
            json={"hypothesis_id": "some-id", "outcome": "invalid_outcome"},
        )
        assert response.status_code == 400
