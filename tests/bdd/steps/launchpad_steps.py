"""Step definitions for Launchpad intelligence BDD scenarios."""

from __future__ import annotations

from behave import given, when, then

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base, set_engine
from engine.launchpad import LaunchpadIntelligence

SAMPLE = {
    "sessions": [
        {"demo_id": "ocp-demo", "partner_id": "p1", "sa_id": "sa1", "lab_code": "lab-a", "config": "gaudi-8b", "status": "completed", "cost": 50.0, "hardware_config": "gaudi", "started_at": "2026-06-01T09:30:00Z"},
        {"demo_id": "ocp-demo", "partner_id": "p1", "sa_id": "sa1", "lab_code": "lab-a", "config": "gaudi-8b", "status": "completed", "cost": 50.0, "hardware_config": "gaudi", "started_at": "2026-06-01T14:00:00Z"},
        {"demo_id": "ai-demo", "partner_id": "p2", "sa_id": "sa2", "lab_code": "lab-b", "config": "xeon6-base", "status": "failed", "cost": 30.0, "hardware_config": "xeon6", "started_at": "2026-06-01T10:15:00Z"},
        {"demo_id": "ai-demo", "partner_id": "p3", "sa_id": "sa2", "lab_code": "lab-b", "config": "xeon6-base", "status": "completed", "cost": 40.0, "hardware_config": "xeon6", "started_at": "2026-06-01T16:00:00Z"},
    ],
    "labs": [{"lab_code": "lab-a"}, {"lab_code": "lab-b"}],
    "capacity": {"total_hours": 168, "configurations": ["gaudi", "xeon6", "cpu-only"]},
    "routing_history": [
        {"workload_type": "inference", "substrate": "gaudi"},
        {"workload_type": "inference", "substrate": "gaudi"},
        {"workload_type": "classification", "substrate": "xeon6"},
        {"workload_type": "check", "substrate": "cpu"},
    ],
}


def _get_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


@given("provisioning data with {count:d} sessions")
def step_sample_data(context, count):
    context.data = SAMPLE
    context.db = _get_db()
    context.intel = LaunchpadIntelligence()


@given("provisioning data with capacity info")
def step_capacity_data(context):
    context.data = SAMPLE
    context.db = _get_db()
    context.intel = LaunchpadIntelligence()


@given("routing history data")
def step_routing_data(context):
    context.data = SAMPLE
    context.db = _get_db()
    context.intel = LaunchpadIntelligence()


@when("demand signals are computed")
def step_compute_demand(context):
    context.result = context.intel.compute_demand_signals(context.data, context.db)


@when("cost attribution is computed")
def step_compute_cost(context):
    context.result = context.intel.compute_cost_attribution(context.data, context.db)


@when("utilization patterns are computed")
def step_compute_utilization(context):
    context.result = context.intel.compute_utilization_patterns(context.data, context.db)


@when("routing intelligence is computed")
def step_compute_routing(context):
    context.result = context.intel.compute_routing_intelligence(context.data, context.db)


@then("the most requested demo is identified")
def step_check_most_requested(context):
    assert len(context.result["most_requested_demos"]) > 0
    assert context.result["most_requested_demos"][0]["demo_id"] == "ocp-demo"


@then("returning partners are identified")
def step_check_returning(context):
    assert "p1" in context.result["returning_partners"]


@then("total cost is {expected:f}")
def step_check_total_cost(context, expected):
    assert context.result["total_cost"] == expected


@then("per-lab costs are calculated")
def step_check_per_lab(context):
    assert len(context.result["per_lab_session"]) > 0


@then("peak demand hours are identified")
def step_check_peak(context):
    assert len(context.result["peak_demand_windows"]) > 0


@then("underutilized configs are identified")
def step_check_underutilized(context):
    assert "cpu-only" in context.result["underutilized_configs"]


@then("gaudi workload types are surfaced")
def step_check_gaudi(context):
    assert len(context.result["gaudi_workloads"]) > 0
    assert context.result["gaudi_workloads"][0]["type"] == "inference"
