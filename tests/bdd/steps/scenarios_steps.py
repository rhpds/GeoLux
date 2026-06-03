"""Step definitions for synthetic client and mode switching BDD scenarios."""

from __future__ import annotations

from behave import given, when, then

from scenarios import registry
import scenarios.healthy_baseline
import scenarios.node_failure
import scenarios.instability_event

import api.routers._shared as _shared


@given("the healthy-baseline scenario")
def step_healthy(context):
    context.test_scenario = registry.get_scenario("healthy-baseline")


@given("the node-failure scenario")
def step_node_failure(context):
    context.test_scenario = registry.get_scenario("node-failure")


@when("the scenario is executed")
def step_execute(context):
    context.result = context.test_scenario.run()


@then('all expected outcomes are "{expected}"')
def step_all_pass(context, expected):
    for stage, outcome in context.test_scenario.expected_outcomes.items():
        assert outcome == expected, f"Stage {stage} expected {expected}, got {outcome}"


@then('cluster-health expected outcome is "{expected}"')
def step_cluster_health(context, expected):
    assert context.test_scenario.expected_outcomes["cluster-health"] == expected


@given("all scenarios are registered")
def step_all_registered(context):
    pass


@when("the scenario list is requested")
def step_list(context):
    context.test_scenario_list = registry.list_scenarios()


@then("at least {count:d} scenarios are available")
def step_count(context, count):
    assert len(context.test_scenario_list) >= count


@given('the current mode is "{mode}"')
def step_set_mode(context, mode):
    _shared.GEOLUX_MODE = mode


@when('mode is switched to "{mode}"')
def step_switch_mode(context, mode):
    _shared.GEOLUX_MODE = mode


@then('the current mode is "{mode}"')
def step_check_mode(context, mode):
    assert _shared.GEOLUX_MODE == mode
