"""Step definitions for Hypothesis Engine BDD scenarios."""

from __future__ import annotations

import json

from behave import given, when, then

from engine.hypothesis import (
    rank_hypotheses,
    validate_hypothesis,
    _parse_hypotheses,
)


@given("an evidence bundle with cluster health data")
def step_evidence_bundle(context):
    context.evidence = {
        "cpu_percent": 85,
        "memory_percent": 70,
        "pods_running": 12,
        "nodes_healthy": True,
    }


@when("hypotheses are generated")
def step_generate_hypotheses(context):
    context.hypotheses = [
        {
            "claim": "CPU usage is elevated",
            "testable_conditions": [
                {"field": "cpu_percent", "operator": "gt", "value": 80}
            ],
            "confidence_score": 0.8,
            "geometric_stability_score": 0.9,
        },
        {
            "claim": "Memory is within normal range",
            "testable_conditions": [
                {"field": "memory_percent", "operator": "lt", "value": 85}
            ],
            "confidence_score": 0.7,
            "geometric_stability_score": 0.85,
        },
    ]
    context.ranked = rank_hypotheses(context.hypotheses)


@then("the result contains structured hypotheses")
def step_has_hypotheses(context):
    assert len(context.ranked) > 0


@then("each hypothesis has a claim and testable conditions")
def step_hypothesis_structure(context):
    for h in context.ranked:
        assert "claim" in h
        assert "testable_conditions" in h


@then("hypotheses are ranked by stability score")
def step_ranked_by_stability(context):
    for i in range(len(context.ranked) - 1):
        assert (
            context.ranked[i]["geometric_stability_score"]
            >= context.ranked[i + 1]["geometric_stability_score"]
        )


@given('a hypothesis claiming "{claim}"')
def step_hypothesis_claim(context, claim):
    if "cpu" in claim.lower() and "90" in claim:
        context.hypothesis = {
            "testable_conditions": [
                {"field": "cpu", "operator": "gt", "value": 90}
            ]
        }


@given("evidence showing cpu at {value:d}%")
def step_evidence_cpu(context, value):
    context.evidence = {"cpu": value}


@given("evidence with no cpu field")
def step_evidence_no_cpu(context):
    context.evidence = {"memory": 50}


@when("the hypothesis is validated")
def step_validate(context):
    context.outcome = validate_hypothesis(context.hypothesis, context.evidence)


@then('the outcome is "{expected}"')
def step_check_outcome(context, expected):
    assert context.outcome == expected, (
        f"Expected '{expected}', got '{context.outcome}'"
    )


@given("an LLM response with a JSON array of hypotheses")
def step_json_array_response(context):
    context.llm_response = json.dumps([
        {"claim": "h1", "testable_conditions": [{"field": "a", "operator": "eq", "value": 1}], "confidence_score": 0.8},
        {"claim": "h2", "testable_conditions": [], "confidence_score": 0.5},
    ])


@given("an LLM response with code-fenced JSON")
def step_code_fenced_response(context):
    context.llm_response = '```json\n[{"claim": "h1", "testable_conditions": [], "confidence_score": 0.7}]\n```'


@given("an LLM response with invalid JSON")
def step_invalid_response(context):
    context.llm_response = "This is not valid JSON at all"


@when("the response is parsed")
def step_parse_response(context):
    context.parsed = _parse_hypotheses(context.llm_response)


@then("all hypotheses are extracted")
def step_all_extracted(context):
    assert len(context.parsed) > 0


@then("an empty list is returned")
def step_empty_list(context):
    assert context.parsed == []
