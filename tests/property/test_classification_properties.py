"""Property-based tests for constraint classification."""

from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from engine.classification import (
    _evaluate_threshold,
    _evaluate_boolean,
    _evaluate_range,
    _determine_overall_result,
    compute_confidence,
    evaluate_constraint,
)


numeric_value = st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
evidence_value = st.one_of(
    st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.text(min_size=0, max_size=20),
)


class TestThresholdInvariants:
    @given(
        actual=numeric_value,
        threshold_val=numeric_value,
        operator=st.sampled_from(["gt", "gte", "lt", "lte", "eq"]),
    )
    @settings(max_examples=300)
    def test_result_always_valid(self, actual, threshold_val, operator):
        definition = {"field": "x", "operator": operator, "value": threshold_val}
        result = _evaluate_threshold(definition, {"x": actual})
        assert result["result"] in ("pass", "fail")
        assert result["confidence_score"] == 1.0
        assert result["llm_interpretation_used"] is False

    @given(actual=numeric_value, threshold_val=numeric_value)
    @settings(max_examples=200)
    def test_gte_deterministic(self, actual, threshold_val):
        definition = {"field": "x", "operator": "gte", "value": threshold_val}
        r1 = _evaluate_threshold(definition, {"x": actual})
        r2 = _evaluate_threshold(definition, {"x": actual})
        assert r1["result"] == r2["result"]

    def test_missing_field_always_inconclusive(self):
        for op in ("gt", "gte", "lt", "lte", "eq"):
            result = _evaluate_threshold({"field": "x", "operator": op, "value": 0}, {})
            assert result["result"] == "inconclusive"


class TestBooleanInvariants:
    @given(actual=st.booleans(), expected=st.booleans())
    @settings(max_examples=100)
    def test_boolean_deterministic(self, actual, expected):
        r1 = _evaluate_boolean({"field": "x", "value": expected}, {"x": actual})
        r2 = _evaluate_boolean({"field": "x", "value": expected}, {"x": actual})
        assert r1["result"] == r2["result"]

    @given(value=st.booleans())
    @settings(max_examples=50)
    def test_same_value_always_passes(self, value):
        result = _evaluate_boolean({"field": "x", "value": value}, {"x": value})
        assert result["result"] == "pass"


class TestRangeInvariants:
    @given(
        actual=numeric_value,
        min_val=numeric_value,
        max_val=numeric_value,
    )
    @settings(max_examples=300)
    def test_result_always_valid(self, actual, min_val, max_val):
        definition = {"field": "x", "min": min(min_val, max_val), "max": max(min_val, max_val)}
        result = _evaluate_range(definition, {"x": actual})
        assert result["result"] in ("pass", "fail")

    @given(value=numeric_value)
    @settings(max_examples=100)
    def test_value_in_wide_range_always_passes(self, value):
        result = _evaluate_range({"field": "x", "min": -1e10, "max": 1e10}, {"x": value})
        assert result["result"] == "pass"


class TestOverallResultInvariants:
    @given(results=st.lists(
        st.sampled_from([
            {"result": "pass"},
            {"result": "fail"},
            {"result": "inconclusive"},
            {"result": "unclassifiable"},
        ]),
        min_size=1,
        max_size=10,
    ))
    @settings(max_examples=200)
    def test_overall_always_valid(self, results):
        overall = _determine_overall_result(results)
        assert overall in ("pass", "fail", "inconclusive", "unclassifiable")

    @given(results=st.lists(
        st.sampled_from([
            {"result": "pass"},
            {"result": "fail"},
            {"result": "inconclusive"},
            {"result": "unclassifiable"},
        ]),
        min_size=1,
        max_size=10,
    ))
    @settings(max_examples=200)
    def test_fail_dominates(self, results):
        overall = _determine_overall_result(results)
        if any(r["result"] == "fail" for r in results):
            assert overall == "fail"


class TestConfidenceInvariants:
    @given(
        ev=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        strength=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        stability=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_confidence_in_unit_range(self, ev, strength, stability, weight):
        result = compute_confidence(ev, strength, stability, weight)
        assert 0.0 <= result <= 1.0
