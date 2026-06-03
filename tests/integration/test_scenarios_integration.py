"""Integration tests for synthetic client, scenarios, and mode switching."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from scenarios import registry
from scenarios.base import Scenario


@pytest.fixture(autouse=True)
def _load_scenarios():
    import scenarios.healthy_baseline
    import scenarios.node_failure
    import scenarios.instability_event


@pytest.fixture
def sc_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestScenarioRegistry:
    def test_list_scenarios(self):
        scenarios = registry.list_scenarios()
        names = {s["name"] for s in scenarios}
        assert "healthy-baseline" in names
        assert "node-failure" in names
        assert "instability-event" in names

    def test_get_existing_scenario(self):
        s = registry.get_scenario("healthy-baseline")
        assert s is not None
        assert s.name == "healthy-baseline"

    def test_get_nonexistent_returns_none(self):
        assert registry.get_scenario("does-not-exist") is None


class TestHealthyBaseline:
    def test_generates_healthy_state(self):
        s = registry.get_scenario("healthy-baseline")
        state = s.generate_state()
        assert state["cluster-health"]["cluster_reachable"] is True
        assert state["cluster-health"]["cpu_percent"] < 80

    def test_generates_evidence_per_stage(self):
        s = registry.get_scenario("healthy-baseline")
        evidence = s.generate_evidence()
        assert "cluster-health" in evidence
        assert "namespace-ready" in evidence

    def test_expected_outcomes_all_pass(self):
        s = registry.get_scenario("healthy-baseline")
        for stage, expected in s.expected_outcomes.items():
            assert expected == "pass"

    def test_run_produces_complete_result(self):
        s = registry.get_scenario("healthy-baseline")
        result = s.run()
        assert result["scenario"] == "healthy-baseline"
        assert "state" in result
        assert "evidence" in result
        assert "stability_profile" in result


class TestNodeFailure:
    def test_generates_failure_state(self):
        s = registry.get_scenario("node-failure")
        state = s.generate_state()
        assert state["cluster-health"]["cpu_percent"] > 90
        assert state["cluster-health"]["healthy_node_ratio"] < 0.8

    def test_expected_cluster_health_fail(self):
        s = registry.get_scenario("node-failure")
        assert s.expected_outcomes["cluster-health"] == "fail"


class TestInstabilityEvent:
    def test_stability_profile_shows_instability(self):
        s = registry.get_scenario("instability-event")
        profile = s.generate_stability_profile()
        assert profile["mean_score"] < 0.5


class TestModeSwitching:
    def test_get_mode(self, client):
        response = client.get("/mode")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] in ("live", "synthetic", "replay")
        assert "valid_modes" in data

    def test_set_valid_mode(self, client):
        response = client.put("/mode", json={"mode": "synthetic"})
        assert response.status_code == 200
        assert response.json()["mode"] == "synthetic"

        response = client.put("/mode", json={"mode": "replay"})
        assert response.status_code == 200
        assert response.json()["mode"] == "replay"

        client.put("/mode", json={"mode": "live"})

    def test_set_invalid_mode_rejected(self, client):
        response = client.put("/mode", json={"mode": "invalid"})
        assert response.status_code == 400

    def test_health_shows_mode(self, client):
        response = client.get("/health")
        assert "mode" in response.json()

    def test_mode_header_present(self, client):
        response = client.get("/health")
        assert "x-geolux-mode" in response.headers


class TestScenarioAPIEndpoints:
    def test_list_scenarios_api(self, client):
        response = client.get("/scenarios/list")
        assert response.status_code == 200
        data = response.json()
        assert len(data["scenarios"]) >= 3

    def test_replay_requires_replay_mode(self, client):
        client.put("/mode", json={"mode": "live"})
        response = client.post("/scenarios/replay/start", json={
            "archive_name": "test-archive",
        })
        assert response.status_code == 409
        client.put("/mode", json={"mode": "live"})
