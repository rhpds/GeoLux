"""Unit tests for evidence-based constraint classification engine."""

import pytest

from engine.classification import (
    _evaluate_boolean,
    _evaluate_composite,
    _evaluate_pattern,
    _evaluate_range,
    _evaluate_threshold,
    _determine_overall_result,
    compute_confidence,
)


class TestEvaluateThreshold:
    def test_gte_pass(self):
        result = _evaluate_threshold({"field": "cpu", "operator": "gte", "value": 50}, {"cpu": 80})
        assert result["result"] == "pass"
        assert result["confidence_score"] == 1.0
        assert result["llm_interpretation_used"] is False

    def test_gte_fail(self):
        result = _evaluate_threshold({"field": "cpu", "operator": "gte", "value": 50}, {"cpu": 30})
        assert result["result"] == "fail"

    def test_lt_pass(self):
        result = _evaluate_threshold({"field": "errors", "operator": "lt", "value": 10}, {"errors": 5})
        assert result["result"] == "pass"

    def test_eq_pass(self):
        result = _evaluate_threshold({"field": "replicas", "operator": "eq", "value": 3}, {"replicas": 3})
        assert result["result"] == "pass"

    def test_missing_field_inconclusive(self):
        result = _evaluate_threshold({"field": "missing", "operator": "gte", "value": 0}, {})
        assert result["result"] == "inconclusive"
        assert result["confidence_score"] == 0.0


class TestEvaluateBoolean:
    def test_true_expected_true_actual(self):
        result = _evaluate_boolean({"field": "healthy", "value": True}, {"healthy": True})
        assert result["result"] == "pass"

    def test_true_expected_false_actual(self):
        result = _evaluate_boolean({"field": "healthy", "value": True}, {"healthy": False})
        assert result["result"] == "fail"

    def test_missing_field(self):
        result = _evaluate_boolean({"field": "missing", "value": True}, {})
        assert result["result"] == "inconclusive"


class TestEvaluateRange:
    def test_in_range(self):
        result = _evaluate_range({"field": "temp", "min": 20, "max": 80}, {"temp": 50})
        assert result["result"] == "pass"

    def test_below_min(self):
        result = _evaluate_range({"field": "temp", "min": 20, "max": 80}, {"temp": 10})
        assert result["result"] == "fail"

    def test_above_max(self):
        result = _evaluate_range({"field": "temp", "min": 20, "max": 80}, {"temp": 90})
        assert result["result"] == "fail"

    def test_at_boundaries(self):
        result = _evaluate_range({"field": "temp", "min": 20, "max": 80}, {"temp": 20})
        assert result["result"] == "pass"
        result = _evaluate_range({"field": "temp", "min": 20, "max": 80}, {"temp": 80})
        assert result["result"] == "pass"


class TestEvaluatePattern:
    def test_match(self):
        result = _evaluate_pattern({"field": "name", "pattern": r"^pod-\d+"}, {"name": "pod-123"})
        assert result["result"] == "pass"

    def test_no_match(self):
        result = _evaluate_pattern({"field": "name", "pattern": r"^pod-\d+"}, {"name": "svc-abc"})
        assert result["result"] == "fail"

    def test_missing_field(self):
        result = _evaluate_pattern({"field": "missing", "pattern": r".*"}, {})
        assert result["result"] == "inconclusive"


class TestEvaluateComposite:
    def test_all_logic_all_pass(self):
        definition = {
            "logic": "all",
            "assertions": [
                {"type": "boolean", "field": "a", "value": True},
                {"type": "threshold", "field": "b", "operator": "gt", "value": 0},
            ],
        }
        result = _evaluate_composite(definition, {"a": True, "b": 5})
        assert result["result"] == "pass"

    def test_all_logic_one_fails(self):
        definition = {
            "logic": "all",
            "assertions": [
                {"type": "boolean", "field": "a", "value": True},
                {"type": "threshold", "field": "b", "operator": "gt", "value": 10},
            ],
        }
        result = _evaluate_composite(definition, {"a": True, "b": 5})
        assert result["result"] == "fail"

    def test_any_logic_one_passes(self):
        definition = {
            "logic": "any",
            "assertions": [
                {"type": "boolean", "field": "a", "value": True},
                {"type": "threshold", "field": "b", "operator": "gt", "value": 100},
            ],
        }
        result = _evaluate_composite(definition, {"a": True, "b": 5})
        assert result["result"] == "pass"


class TestDetermineOverallResult:
    def test_all_pass(self):
        assert _determine_overall_result([{"result": "pass"}, {"result": "pass"}]) == "pass"

    def test_any_fail(self):
        assert _determine_overall_result([{"result": "pass"}, {"result": "fail"}]) == "fail"

    def test_unclassifiable_without_fail(self):
        assert _determine_overall_result([{"result": "pass"}, {"result": "unclassifiable"}]) == "unclassifiable"

    def test_inconclusive_without_fail_or_unclassifiable(self):
        assert _determine_overall_result([{"result": "pass"}, {"result": "inconclusive"}]) == "inconclusive"

    def test_fail_takes_priority(self):
        assert _determine_overall_result([{"result": "fail"}, {"result": "unclassifiable"}, {"result": "inconclusive"}]) == "fail"


class TestComputeConfidence:
    def test_full_confidence(self):
        assert compute_confidence(1.0, 1.0, 1.0) == 1.0

    def test_zero_stability_with_weight(self):
        confidence = compute_confidence(1.0, 1.0, 0.0, stability_weight=0.5)
        assert confidence == 0.5

    def test_stability_weight_zero(self):
        confidence = compute_confidence(0.8, 0.6, 0.0, stability_weight=0.0)
        assert confidence == pytest.approx(0.7)
