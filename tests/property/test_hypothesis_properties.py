"""Property-based tests for Hypothesis Engine."""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from engine.hypothesis import rank_hypotheses, validate_hypothesis


hypothesis_st = st.fixed_dictionaries({
    "claim": st.text(min_size=1, max_size=100),
    "geometric_stability_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    "confidence_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
})

condition_st = st.fixed_dictionaries({
    "field": st.sampled_from(["cpu", "memory", "status", "count"]),
    "operator": st.sampled_from(["eq", "gt", "lt", "gte", "lte"]),
    "value": st.one_of(st.integers(min_value=0, max_value=100), st.text(min_size=1, max_size=10)),
})


class TestRankingProperties:
    @given(hypotheses=st.lists(hypothesis_st, min_size=0, max_size=20))
    @settings(max_examples=200)
    def test_ranking_preserves_all_elements(self, hypotheses):
        ranked = rank_hypotheses(hypotheses)
        assert len(ranked) == len(hypotheses)

    @given(hypotheses=st.lists(hypothesis_st, min_size=2, max_size=20))
    @settings(max_examples=200)
    def test_ranking_is_sorted_descending(self, hypotheses):
        ranked = rank_hypotheses(hypotheses)
        for i in range(len(ranked) - 1):
            key_i = (ranked[i]["geometric_stability_score"], ranked[i]["confidence_score"])
            key_j = (ranked[i + 1]["geometric_stability_score"], ranked[i + 1]["confidence_score"])
            assert key_i >= key_j

    @given(hypotheses=st.lists(hypothesis_st, min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_ranking_is_deterministic(self, hypotheses):
        r1 = rank_hypotheses(hypotheses)
        r2 = rank_hypotheses(hypotheses)
        assert r1 == r2

    @given(hypotheses=st.lists(hypothesis_st, min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_ranking_is_idempotent(self, hypotheses):
        ranked_once = rank_hypotheses(hypotheses)
        ranked_twice = rank_hypotheses(ranked_once)
        assert ranked_once == ranked_twice


class TestValidationProperties:
    @given(
        conditions=st.lists(condition_st, min_size=1, max_size=5),
        evidence=st.dictionaries(
            keys=st.sampled_from(["cpu", "memory", "status", "count"]),
            values=st.one_of(st.integers(0, 100), st.text(min_size=1, max_size=10)),
            min_size=0,
            max_size=4,
        ),
    )
    @settings(max_examples=200)
    def test_validation_always_returns_valid_outcome(self, conditions, evidence):
        hypothesis = {"testable_conditions": conditions}
        outcome = validate_hypothesis(hypothesis, evidence)
        assert outcome in ("validated", "falsified", "inconclusive")

    @given(
        conditions=st.lists(condition_st, min_size=1, max_size=3),
        evidence=st.dictionaries(
            keys=st.sampled_from(["cpu", "memory", "status", "count"]),
            values=st.one_of(st.integers(0, 100), st.text(min_size=1, max_size=10)),
            min_size=0,
            max_size=4,
        ),
    )
    @settings(max_examples=200)
    def test_validation_is_deterministic(self, conditions, evidence):
        hypothesis = {"testable_conditions": conditions}
        r1 = validate_hypothesis(hypothesis, evidence)
        r2 = validate_hypothesis(hypothesis, evidence)
        assert r1 == r2

    def test_empty_conditions_always_inconclusive(self):
        assert validate_hypothesis({"testable_conditions": []}, {"any": "data"}) == "inconclusive"
        assert validate_hypothesis({}, {}) == "inconclusive"
