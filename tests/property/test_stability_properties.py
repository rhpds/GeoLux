"""Property-based tests for geometric stability measurement.

Uses Hypothesis to verify invariants hold across all inputs.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from api.stability.measure import (
    StabilityState,
    compute_logit_entropy,
    compute_perplexity,
    compute_stability_score,
    compute_token_probability_variance,
    determine_stability_state,
    _normalize_score,
)

logprob_value = st.floats(min_value=-20.0, max_value=0.0, allow_nan=False, allow_infinity=False)
logprob_step = st.lists(logprob_value, min_size=1, max_size=10)
logprob_sequence = st.lists(logprob_step, min_size=0, max_size=20)

stability_score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
threshold = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


class TestStabilityScoreInvariants:
    @given(logprobs=logprob_sequence)
    @settings(max_examples=200)
    def test_token_probability_score_always_in_unit_range(self, logprobs):
        score = compute_token_probability_variance(logprobs)
        assert 0.0 <= score <= 1.0

    @given(logprobs=logprob_sequence)
    @settings(max_examples=200)
    def test_logit_entropy_score_always_in_unit_range(self, logprobs):
        score = compute_logit_entropy(logprobs)
        assert 0.0 <= score <= 1.0

    @given(logprobs=logprob_sequence)
    @settings(max_examples=200)
    def test_perplexity_score_always_in_unit_range(self, logprobs):
        score = compute_perplexity(logprobs)
        assert 0.0 <= score <= 1.0

    @given(logprobs=logprob_sequence, method=st.sampled_from(["token_probability", "logit_entropy", "perplexity"]))
    @settings(max_examples=200)
    def test_compute_stability_score_always_in_unit_range(self, logprobs, method):
        score = compute_stability_score(logprobs, method)
        assert 0.0 <= score <= 1.0

    def test_empty_logprobs_always_returns_default(self):
        empty = []
        assert compute_token_probability_variance(empty) == 0.5
        assert compute_logit_entropy(empty) == 0.5
        assert compute_perplexity(empty) == 0.5


class TestStabilityStateDeterminism:
    @given(score=stability_score, correct=st.booleans(), thresh=threshold)
    @settings(max_examples=500)
    def test_state_is_deterministic(self, score, correct, thresh):
        state1 = determine_stability_state(score, correct, thresh)
        state2 = determine_stability_state(score, correct, thresh)
        assert state1 == state2

    @given(score=stability_score, correct=st.booleans(), thresh=threshold)
    @settings(max_examples=500)
    def test_state_is_always_one_of_four(self, score, correct, thresh):
        state = determine_stability_state(score, correct, thresh)
        assert state in (
            StabilityState.STABLE_PASS,
            StabilityState.STABLE_FAIL,
            StabilityState.UNSTABLE_PASS,
            StabilityState.UNSTABLE_FAIL,
        )

    @given(score=stability_score, thresh=threshold)
    @settings(max_examples=200)
    def test_correct_output_never_produces_fail_state(self, score, thresh):
        state = determine_stability_state(score, True, thresh)
        assert state in (StabilityState.STABLE_PASS, StabilityState.UNSTABLE_PASS)

    @given(score=stability_score, thresh=threshold)
    @settings(max_examples=200)
    def test_incorrect_output_never_produces_pass_state(self, score, thresh):
        state = determine_stability_state(score, False, thresh)
        assert state in (StabilityState.STABLE_FAIL, StabilityState.UNSTABLE_FAIL)

    @given(thresh=threshold)
    @settings(max_examples=100)
    def test_above_threshold_always_stable(self, thresh):
        assume(thresh < 1.0)
        score = thresh + 0.001
        assume(score <= 1.0)
        state = determine_stability_state(score, True, thresh)
        assert state == StabilityState.STABLE_PASS

    @given(thresh=threshold)
    @settings(max_examples=100)
    def test_below_threshold_always_unstable(self, thresh):
        assume(thresh > 0.0)
        score = thresh - 0.001
        assume(score >= 0.0)
        state = determine_stability_state(score, True, thresh)
        assert state == StabilityState.UNSTABLE_PASS


class TestNormalizationInvariants:
    @given(value=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
           scale=st.floats(min_value=0.01, max_value=100.0, allow_nan=False))
    @settings(max_examples=200)
    def test_normalized_always_in_unit_range(self, value, scale):
        result = _normalize_score(value, lower_is_better=True, scale=scale)
        assert 0.0 <= result <= 1.0

        result2 = _normalize_score(value, lower_is_better=False, scale=scale)
        assert 0.0 <= result2 <= 1.0
