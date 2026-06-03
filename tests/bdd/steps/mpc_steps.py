"""Step definitions for LLM-MPC BDD scenarios."""

from __future__ import annotations

from behave import given, when, then

from engine.mpc import MPCController


@given("stability scores of {s1:f} and {s2:f}")
def step_two_scores(context, s1, s2):
    context.stability_scores = [s1, s2]
    context.controller = MPCController(default_horizon=2, max_horizon=5)


@given("stability scores of {s1:f}, {s2:f}, and {s3:f}")
def step_three_scores(context, s1, s2, s3):
    context.stability_scores = [s1, s2, s3]
    context.controller = MPCController(default_horizon=2, max_horizon=5)


@given("current horizon is {h:d}")
def step_current_horizon(context, h):
    context.current_horizon = h


@given("current horizon is {h:d} with max {m:d}")
def step_horizon_with_max(context, h, m):
    context.current_horizon = h
    context.controller.max_horizon = m


@when("the horizon is adjusted")
def step_adjust_horizon(context):
    context.new_horizon = context.controller.adjust_horizon(
        context.stability_scores, context.current_horizon
    )


@then("the horizon remains {expected:d}")
def step_horizon_unchanged(context, expected):
    assert context.new_horizon == expected, f"Expected {expected}, got {context.new_horizon}"


@then("the horizon is less than {val:d}")
def step_horizon_less_than(context, val):
    assert context.new_horizon < val, f"Expected < {val}, got {context.new_horizon}"


@then("the horizon is {expected:d}")
def step_horizon_exact(context, expected):
    assert context.new_horizon == expected, f"Expected {expected}, got {context.new_horizon}"


@given("{n:d} consecutive unstable prediction cycles")
def step_consecutive_instabilities(context, n):
    context.controller = MPCController()
    context.controller._suspension_threshold = n
    for _ in range(n):
        context.controller._check_suspension([0.3])


@when("suspension is checked")
def step_check_suspension(context):
    context.suspended = context.controller._check_suspension([0.3])


@then("MPC is suspended")
def step_is_suspended(context):
    assert context.suspended is True


@given("an objective to scale to {target:d} replicas")
def step_scale_objective(context, target):
    context.controller = MPCController()
    context.objective = {"type": "scale", "target": target}


@when("candidates are generated")
def step_generate_candidates(context):
    context.candidates = context.controller._generate_candidates({}, context.objective)


@then("a scale_replicas action is produced")
def step_scale_action(context):
    assert any(c["action_type"] == "scale_replicas" for c in context.candidates)
