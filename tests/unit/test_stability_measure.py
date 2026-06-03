"""Unit tests for geometric stability measurement functions."""

import math

import pytest

from api.stability.measure import (
    StabilityMethod,
    StabilityState,
    compute_logit_entropy,
    compute_perplexity,
    compute_stability_score,
    compute_token_probability_variance,
    determine_stability_state,
)


class TestComputeTokenProbabilityVariance:
    def test_empty_logprobs_returns_default(self):
        assert compute_token_probability_variance([]) == 0.5

    def test_uniform_logprobs_high_stability(self):
        logprobs = [[-0.1, -0.1, -0.1]] * 10
        score = compute_token_probability_variance(logprobs)
        assert score >= 0.9

    def test_varied_logprobs_lower_stability(self):
        logprobs = [[-0.01, -5.0, -10.0]] * 10
        score = compute_token_probability_variance(logprobs)
        assert 0.0 <= score <= 1.0

    def test_score_always_in_range(self):
        test_cases = [
            [[-0.5, -1.0]],
            [[-0.01, -100.0]],
            [[-1.0, -1.0, -1.0, -1.0, -1.0]],
        ]
        for logprobs in test_cases:
            score = compute_token_probability_variance(logprobs)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for {logprobs}"


class TestComputeLogitEntropy:
    def test_empty_logprobs_returns_default(self):
        assert compute_logit_entropy([]) == 0.5

    def test_concentrated_distribution_high_stability(self):
        logprobs = [[math.log(0.99), math.log(0.005), math.log(0.005)]] * 5
        score = compute_logit_entropy(logprobs)
        assert score >= 0.5

    def test_score_always_in_range(self):
        logprobs = [[math.log(0.5), math.log(0.3), math.log(0.2)]] * 3
        score = compute_logit_entropy(logprobs)
        assert 0.0 <= score <= 1.0


class TestComputePerplexity:
    def test_empty_logprobs_returns_default(self):
        assert compute_perplexity([]) == 0.5

    def test_high_confidence_logprobs(self):
        logprobs = [[-0.01, -5.0]] * 10
        score = compute_perplexity(logprobs)
        assert score >= 0.9

    def test_score_always_in_range(self):
        logprobs = [[-2.0, -3.0]] * 5
        score = compute_perplexity(logprobs)
        assert 0.0 <= score <= 1.0


class TestComputeStabilityScore:
    def test_token_probability_method(self):
        logprobs = [[-0.1, -0.1]] * 5
        score = compute_stability_score(logprobs, "token_probability")
        assert 0.0 <= score <= 1.0

    def test_logit_entropy_method(self):
        logprobs = [[math.log(0.9), math.log(0.1)]] * 5
        score = compute_stability_score(logprobs, "logit_entropy")
        assert 0.0 <= score <= 1.0

    def test_perplexity_method(self):
        logprobs = [[-0.1, -5.0]] * 5
        score = compute_stability_score(logprobs, "perplexity")
        assert 0.0 <= score <= 1.0

    def test_unknown_method_returns_default(self):
        score = compute_stability_score([], "unknown_method")
        assert score == 0.5


class TestDetermineStabilityState:
    def test_stable_pass(self):
        state = determine_stability_state(0.8, True, 0.7)
        assert state == StabilityState.STABLE_PASS

    def test_stable_fail(self):
        state = determine_stability_state(0.8, False, 0.7)
        assert state == StabilityState.STABLE_FAIL

    def test_unstable_pass(self):
        state = determine_stability_state(0.5, True, 0.7)
        assert state == StabilityState.UNSTABLE_PASS

    def test_unstable_fail(self):
        state = determine_stability_state(0.5, False, 0.7)
        assert state == StabilityState.UNSTABLE_FAIL

    def test_at_threshold_is_stable(self):
        state = determine_stability_state(0.7, True, 0.7)
        assert state == StabilityState.STABLE_PASS

    def test_just_below_threshold_is_unstable(self):
        state = determine_stability_state(0.699, True, 0.7)
        assert state == StabilityState.UNSTABLE_PASS

    def test_deterministic_for_same_inputs(self):
        for _ in range(100):
            assert determine_stability_state(0.8, True) == StabilityState.STABLE_PASS
            assert determine_stability_state(0.3, False) == StabilityState.UNSTABLE_FAIL
