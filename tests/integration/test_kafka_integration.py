"""Integration tests for Kafka consumer pipeline.

Tests that Stargate evaluation events consumed from Kafka flow through
the GeoLux classification + hypothesis pipeline correctly.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db import repository


@pytest.fixture
def kafka_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestStargateEvaluationHandler:
    """Tests the handler that processes stargate-evaluations Kafka messages."""

    def _make_stargate_message(self, outcome="fail", stage="cluster-health", **overrides):
        """Create a message matching Stargate's actual Kafka publish format."""
        msg = {
            "event_type": f"evaluation.{outcome}ed" if outcome != "warn" else "evaluation.warned",
            "run_id": "run-kafka-test",
            "stage_id": stage,
            "lab_code": "ocp4-showroom",
            "cluster_name": "infra01",
            "outcome": outcome,
            "failure_class": "cluster_overloaded" if outcome == "fail" else "",
            "message": "Test evaluation",
            "_kafka_topic": "stargate-evaluations",
            "_published_at": "2026-06-03T19:00:00Z",
        }
        msg.update(overrides)
        return msg

    def test_processes_flat_stargate_message(self, kafka_db):
        """Stargate publishes flat dicts, not wrapped in {payload: ...}."""
        from api.routers.integration import StarGateEvent, process_stargate_event

        msg = self._make_stargate_message(outcome="fail")

        event = StarGateEvent(
            source="stargate-kafka",
            event_type=msg.get("event_type", ""),
            event_id=msg.get("event_id"),
            timestamp=msg.get("_published_at"),
            payload=msg,
        )

        result = process_stargate_event(event, kafka_db)
        assert result.processed is True
        assert result.classification_result in ("fail", "inconclusive", "pass")

    def test_processes_pass_event(self, kafka_db):
        from api.routers.integration import StarGateEvent, process_stargate_event

        msg = self._make_stargate_message(outcome="pass")

        event = StarGateEvent(
            source="stargate-kafka",
            event_type=msg["event_type"],
            payload=msg,
        )

        result = process_stargate_event(event, kafka_db)
        assert result.processed is True

    def test_handler_function_matches_kafka_format(self, kafka_db):
        """Test the actual handler function that would be called by KafkaConsumerManager."""
        msg = self._make_stargate_message(
            outcome="fail",
            cluster_name="ocpv05",
            failure_class="pod_crashloop",
        )

        from api.routers.integration import StarGateEvent, process_stargate_event

        payload = msg.get("payload", msg)
        event = StarGateEvent(
            source="stargate-kafka",
            event_type=msg.get("event_type", ""),
            event_id=msg.get("event_id"),
            timestamp=msg.get("_published_at", msg.get("timestamp")),
            payload=payload if isinstance(payload, dict) else {"raw": payload},
        )

        result = process_stargate_event(event, kafka_db)
        assert result.processed is True
        assert result.event_id is not None

    def test_classification_runs_on_kafka_event(self, kafka_db):
        """Verify the classification pipeline actually evaluates constraints."""
        from constraints.loader import sync_constraints_to_db
        from pathlib import Path
        sync_constraints_to_db(kafka_db, Path("constraints/stages"))

        from api.routers.integration import StarGateEvent, process_stargate_event

        msg = self._make_stargate_message(
            outcome="fail",
            cluster_name="infra01",
        )
        msg["criteria_results"] = {
            "cluster_reachable": True,
            "cpu_percent": 95,
            "memory_percent": 92,
            "healthy_node_ratio": 0.4,
        }

        event = StarGateEvent(
            source="stargate-kafka",
            event_type=msg["event_type"],
            payload=msg,
        )

        result = process_stargate_event(event, kafka_db)
        assert result.processed is True
        assert result.classification_result == "fail"


class TestKafkaIntegrationEndpoint:
    """Tests the HTTP /integration/events endpoint with Stargate event formats."""

    def test_flat_stargate_event(self, client):
        response = client.post("/integration/events", json={
            "source": "stargate",
            "event_type": "evaluation.failed",
            "event_id": "kafka-int-001",
            "payload": {
                "run_id": "run-001",
                "stage_id": "cluster-health",
                "lab_code": "ocp4-showroom",
                "cluster": "infra01",
                "outcome": "fail",
                "failure_class": "cluster_overloaded",
            }
        })
        assert response.status_code == 201
        data = response.json()
        assert data["processed"] is True

    def test_event_with_criteria_results(self, client):
        response = client.post("/integration/events", json={
            "source": "stargate",
            "event_type": "evaluation.failed",
            "payload": {
                "run_id": "run-002",
                "stage_id": "cluster-health",
                "cluster": "infra01",
                "outcome": "fail",
                "criteria_results": {
                    "cluster_reachable": True,
                    "cpu_percent": 97,
                    "memory_percent": 94,
                    "healthy_node_ratio": 0.3,
                }
            }
        })
        assert response.status_code == 201
        assert response.json()["classification_result"] is not None

    def test_pass_event_skips_hypothesis(self, client):
        response = client.post("/integration/events", json={
            "source": "stargate",
            "event_type": "evaluation.passed",
            "payload": {
                "run_id": "run-003",
                "stage_id": "cluster-health",
                "cluster": "infra01",
                "outcome": "pass",
            }
        })
        assert response.status_code == 201
        assert response.json()["hypotheses_generated"] == 0
