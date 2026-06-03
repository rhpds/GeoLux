"""Step definitions for Deepfield BDD scenarios."""

from __future__ import annotations

from behave import given, when, then

from engine.deepfield import DeepfieldRouter, TIER_SUBSTRATE_MAP
from db.models import TierAssignment, Substrate


@given("a workload with no reasoning required")
def step_simple_workload(context):
    context.description = {"task_type": "check_status", "reasoning_required": False}
    context.router = DeepfieldRouter()


@given("a workload that is novel and multi-step")
def step_complex_workload(context):
    context.description = {"task_type": "root_cause", "novel": True, "multi_step": True, "reasoning_required": True}
    context.router = DeepfieldRouter()


@when("the workload is classified by rules")
def step_rule_classify(context):
    context.tier, context.confidence, context.rule = context.router._rule_based_classify(context.description)
    context.substrate = TIER_SUBSTRATE_MAP[context.tier]


@then('the tier is "{tier}" with substrate "{substrate}"')
def step_check_tier_substrate(context, tier, substrate):
    assert context.tier.value == tier, f"Expected tier {tier}, got {context.tier.value}"
    assert context.substrate.value == substrate, f"Expected substrate {substrate}, got {context.substrate.value}"


@given("a routing request with override but no reason")
def step_override_no_reason(context):
    context.router = DeepfieldRouter()
    context.request = {
        "workload_id": "test",
        "workload_description": {},
        "override_tier": "macro",
    }


@then("the routing is rejected")
def step_routing_rejected(context):
    class FakeDB:
        def add(self, *a): pass
        def flush(self): pass
        def commit(self): pass
        def query(self, *a): return self
        def filter(self, *a): return self
        def order_by(self, *a): return self
        def limit(self, *a): return self
        def all(self): return []

    result = context.router.route(context.request, FakeDB())
    assert "error" in result


@given("an unstable classification result for nano tier")
def step_unstable_nano(context):
    context.router = DeepfieldRouter()
    context.tier = TierAssignment.NANO


@when("safety escalation is applied")
def step_apply_escalation(context):
    context.escalated = context.router._escalate_for_safety(context.tier)


@then('the tier is escalated to "{tier}"')
def step_check_escalated(context, tier):
    assert context.escalated.value == tier


@given("a macro workload and gaudi is unavailable")
def step_macro_no_gaudi(context):
    context.router = DeepfieldRouter()
    context.tier = TierAssignment.MACRO


@when("fallback policy is applied")
def step_apply_fallback(context):
    context.fb_tier, context.fb_substrate = context.router._apply_fallback(context.tier)


@then("the workload routes to nano with cpu")
def step_check_fallback(context):
    assert context.fb_tier == TierAssignment.NANO
    assert context.fb_substrate == Substrate.CPU


@given("{count:d} observations with value {value:d} against threshold {threshold:d}")
def step_seed_observations(context, count, value, threshold):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.database import Base, set_engine
    from engine.nanoobs import NanoObsCollector

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    context.obs_db = Session()
    context.collector = NanoObsCollector()
    context.threshold = float(threshold)

    for _ in range(count):
        context.collector.observe("cluster-bdd", "agent-bdd", "t-bdd", float(value), float(threshold), context.obs_db)


@when("a new observation is recorded")
def step_new_observation(context):
    context.obs_result = context.collector.observe(
        "cluster-bdd", "agent-bdd", "t-bdd", 96.0, context.threshold, context.obs_db
    )


@then("drift is detected")
def step_drift_detected(context):
    assert context.obs_result["drift_detected"] is True


@then("an adjustment is recommended")
def step_adjustment_recommended(context):
    assert context.obs_result["adjustment_recommended"] is True


@given("a recommended threshold adjustment")
def step_recommended_adjustment(context):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.database import Base, set_engine
    from engine.nanoobs import NanoObsCollector

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    context.obs_db = Session()
    context.collector = NanoObsCollector()

    for _ in range(10):
        context.collector.observe("cluster-approve", "agent-a", "t-a", 95.0, 80.0, context.obs_db)
    context.obs_result = context.collector.observe("cluster-approve", "agent-a", "t-a", 96.0, 80.0, context.obs_db)


@when("the adjustment is approved by an operator")
def step_approve_adjustment(context):
    context.approved = context.collector.approve_adjustment(
        context.obs_result["observation_id"], "operator@test.com", context.obs_db
    )


@then("the approval is recorded with the operator name")
def step_approval_recorded(context):
    assert context.approved is True
