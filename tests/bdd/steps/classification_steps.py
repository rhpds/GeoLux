"""Step definitions for classification BDD scenarios."""

from __future__ import annotations

from unittest.mock import MagicMock

from behave import given, when, then

from engine.classification import (
    _evaluate_threshold,
    _evaluate_boolean,
    _evaluate_range,
    _determine_overall_result,
    evaluate_constraint,
)


@given("constraint definitions for cluster-health stage")
def step_cluster_health_constraints(context):
    context.constraints = [
        _make_constraint("ch-001", "boolean", {"field": "cluster_reachable", "value": True}, ["cluster_reachable"]),
        _make_constraint("ch-002", "threshold", {"field": "cpu_percent", "operator": "lte", "value": 85}, ["cpu_percent"]),
        _make_constraint("ch-003", "threshold", {"field": "memory_percent", "operator": "lte", "value": 90}, ["memory_percent"]),
    ]


@given("evidence showing a healthy cluster")
def step_healthy_evidence(context):
    context.evidence = {"cluster_reachable": True, "cpu_percent": 50, "memory_percent": 60}


@given("evidence showing cluster unreachable")
def step_unreachable_evidence(context):
    context.evidence = {"cluster_reachable": False, "cpu_percent": 50, "memory_percent": 60}


@given("evidence with missing fields")
def step_missing_evidence(context):
    context.evidence = {"cluster_reachable": True}


@when("evidence is classified")
def step_classify(context):
    context.results = []
    for c in context.constraints:
        result = evaluate_constraint(c, context.evidence)
        context.results.append(result)
    context.overall = _determine_overall_result(context.results)


@then('the overall result is "{expected}"')
def step_check_overall(context, expected):
    assert context.overall == expected, f"Expected '{expected}', got '{context.overall}'"


@then("all individual constraints pass")
def step_all_pass(context):
    for r in context.results:
        assert r["result"] == "pass", f"Constraint failed: {r}"


@then('at least one constraint is "{expected}"')
def step_at_least_one(context, expected):
    assert any(r["result"] == expected for r in context.results)


@given("a threshold constraint requiring cpu below {value:d}")
def step_threshold_constraint(context, value):
    context.constraint_def = {"field": "cpu_percent", "operator": "lte", "value": value}
    context.assertion_type = "threshold"


@given("a boolean constraint requiring cluster reachable")
def step_boolean_constraint(context):
    context.constraint_def = {"field": "cluster_reachable", "value": True}
    context.assertion_type = "boolean"


@given("a range constraint requiring status code {min_val:d}-{max_val:d}")
def step_range_constraint(context, min_val, max_val):
    context.constraint_def = {"field": "status_code", "min": min_val, "max": max_val}
    context.assertion_type = "range"


@given("evidence with cpu at {value:d}")
def step_cpu_evidence(context, value):
    context.evidence = {"cpu_percent": value}


@given("evidence with cluster unreachable")
def step_unreachable(context):
    context.evidence = {"cluster_reachable": False}


@given("evidence with status code {value:d}")
def step_status_code(context, value):
    context.evidence = {"status_code": value}


@when("the constraint is evaluated")
def step_evaluate(context):
    if context.assertion_type == "threshold":
        context.eval_result = _evaluate_threshold(context.constraint_def, context.evidence)
    elif context.assertion_type == "boolean":
        context.eval_result = _evaluate_boolean(context.constraint_def, context.evidence)
    elif context.assertion_type == "range":
        context.eval_result = _evaluate_range(context.constraint_def, context.evidence)


@then('the result is "{expected}"')
def step_check_result(context, expected):
    assert context.eval_result["result"] == expected, f"Expected '{expected}', got '{context.eval_result['result']}'"


def _make_constraint(cid, atype, adef, requirements):
    c = MagicMock()
    c.constraint_id = cid
    c.constraint_name = cid
    c.assertion_type = MagicMock()
    c.assertion_type.value = atype
    c.assertion_definition = adef
    c.evidence_requirements = requirements
    c.severity = MagicMock()
    c.severity.value = "major"
    c.geometric_stability_weight = 0.5
    return c
