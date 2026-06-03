"""Integration tests for Launchpad intelligence layer."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db import repository
from engine.launchpad import LaunchpadIntelligence


@pytest.fixture
def lp_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


SAMPLE_DATA = {
    "sessions": [
        {"demo_id": "ocp-demo", "partner_id": "p1", "sa_id": "sa1", "lab_code": "lab-a", "config": "gaudi-8b", "status": "completed", "cost": 50.0, "hardware_config": "gaudi", "started_at": "2026-06-01T09:30:00Z"},
        {"demo_id": "ocp-demo", "partner_id": "p1", "sa_id": "sa1", "lab_code": "lab-a", "config": "gaudi-8b", "status": "completed", "cost": 50.0, "hardware_config": "gaudi", "started_at": "2026-06-01T14:00:00Z"},
        {"demo_id": "ai-demo", "partner_id": "p2", "sa_id": "sa2", "lab_code": "lab-b", "config": "xeon6-base", "status": "failed", "cost": 30.0, "hardware_config": "xeon6", "started_at": "2026-06-01T10:15:00Z"},
        {"demo_id": "ai-demo", "partner_id": "p3", "sa_id": "sa2", "lab_code": "lab-b", "config": "xeon6-base", "status": "completed", "cost": 40.0, "hardware_config": "xeon6", "started_at": "2026-06-01T16:00:00Z"},
    ],
    "labs": [{"lab_code": "lab-a"}, {"lab_code": "lab-b"}],
    "capacity": {
        "total_hours": 168,
        "configurations": ["gaudi", "xeon6", "cpu-only"],
    },
    "routing_history": [
        {"workload_type": "inference", "substrate": "gaudi"},
        {"workload_type": "inference", "substrate": "gaudi"},
        {"workload_type": "classification", "substrate": "xeon6"},
        {"workload_type": "check", "substrate": "cpu"},
    ],
}


class TestDemandSignals:
    def test_computes_most_requested(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_demand_signals(SAMPLE_DATA, lp_db)
        assert result["most_requested_demos"][0]["demo_id"] == "ocp-demo"
        assert result["most_requested_demos"][0]["count"] == 2

    def test_computes_failure_configs(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_demand_signals(SAMPLE_DATA, lp_db)
        assert len(result["highest_failure_configs"]) == 1
        assert result["highest_failure_configs"][0]["config"] == "xeon6-base"

    def test_identifies_returning_partners(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_demand_signals(SAMPLE_DATA, lp_db)
        assert "p1" in result["returning_partners"]

    def test_persists_to_db(self, lp_db):
        intel = LaunchpadIntelligence()
        intel.compute_demand_signals(SAMPLE_DATA, lp_db)
        records = repository.get_intelligence_records(lp_db, intelligence_type="demand_signal")
        assert len(records) == 1


class TestCostAttribution:
    def test_computes_per_lab(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_cost_attribution(SAMPLE_DATA, lp_db)
        lab_costs = {c["lab_code"]: c["total_cost"] for c in result["per_lab_session"]}
        assert lab_costs["lab-a"] == 100.0

    def test_computes_total(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_cost_attribution(SAMPLE_DATA, lp_db)
        assert result["total_cost"] == 170.0


class TestUtilizationPatterns:
    def test_computes_peak_hours(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_utilization_patterns(SAMPLE_DATA, lp_db)
        assert len(result["peak_demand_windows"]) > 0

    def test_identifies_underutilized(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_utilization_patterns(SAMPLE_DATA, lp_db)
        assert "cpu-only" in result["underutilized_configs"]


class TestRoutingIntelligence:
    def test_computes_gaudi_workloads(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_routing_intelligence(SAMPLE_DATA, lp_db)
        assert result["gaudi_workloads"][0]["type"] == "inference"
        assert result["gaudi_workloads"][0]["count"] == 2

    def test_computes_totals(self, lp_db):
        intel = LaunchpadIntelligence()
        result = intel.compute_routing_intelligence(SAMPLE_DATA, lp_db)
        assert result["total_routed"] == 4


class TestLaunchpadAPIEndpoints:
    def test_get_intelligence_empty(self, client):
        response = client.get("/launchpad/intelligence")
        assert response.status_code == 200

    def test_get_demand_empty(self, client):
        response = client.get("/launchpad/demand")
        assert response.status_code == 200

    def test_get_cost_empty(self, client):
        response = client.get("/launchpad/cost")
        assert response.status_code == 200

    def test_get_utilization_empty(self, client):
        response = client.get("/launchpad/utilization")
        assert response.status_code == 200
