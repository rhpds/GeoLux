"""Step definitions for geometric stability BDD scenarios."""

from behave import given, when, then

from api.stability.measure import (
    compute_stability_score,
    determine_stability_state,
    StabilityState,
)


@given("the stability threshold is {threshold:f}")
def step_set_threshold(context, threshold):
    context.threshold = threshold


@given("an LLM call with low logprob variance")
def step_low_variance_logprobs(context):
    context.logprobs = [[-0.05, -0.06, -0.07, -0.08, -0.09]] * 10


@given("an LLM call with high logprob variance")
def step_high_variance_logprobs(context):
    context.logprobs = [[-0.01, -0.5, -1.0, -3.0, -8.0]] * 10


@given("an LLM call with no logprobs")
def step_no_logprobs(context):
    context.logprobs = []


@when("stability is measured")
def step_measure_stability(context):
    context.score = compute_stability_score(context.logprobs, "token_probability")


@when("the output is correct")
def step_output_correct(context):
    context.outcome_correct = True
    context.state = determine_stability_state(
        context.score, context.outcome_correct, context.threshold
    )


@when("the output is incorrect")
def step_output_incorrect(context):
    context.outcome_correct = False
    context.state = determine_stability_state(
        context.score, context.outcome_correct, context.threshold
    )


@when("the stability threshold is set to {threshold:f}")
def step_update_threshold(context, threshold):
    context.new_threshold = threshold
    if 0.0 <= threshold <= 1.0:
        context.threshold = threshold
        context.update_rejected = False
    else:
        context.update_rejected = True


@then('the stability state is "{expected_state}"')
def step_check_state(context, expected_state):
    assert context.state.value == expected_state, (
        f"Expected {expected_state}, got {context.state.value}"
    )


@then("the stability score is above the threshold")
def step_score_above_threshold(context):
    assert context.score >= context.threshold, (
        f"Score {context.score} not above threshold {context.threshold}"
    )


@then("the stability score is below the threshold")
def step_score_below_threshold(context):
    assert context.score < context.threshold, (
        f"Score {context.score} not below threshold {context.threshold}"
    )


@then("the stability score is {expected:f}")
def step_score_exact(context, expected):
    assert context.score == expected, (
        f"Expected score {expected}, got {context.score}"
    )


@then("the stability threshold is {expected:f}")
def step_check_threshold(context, expected):
    assert context.threshold == expected


@then("the update is rejected with a validation error")
def step_update_rejected(context):
    assert context.update_rejected is True
