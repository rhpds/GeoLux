"""Unit tests for hypothesis engine."""

import json

import pytest

from engine.hypothesis import (
    rank_hypotheses,
    validate_hypothesis,
    _parse_hypotheses,
    _normalize_hypothesis,
    check_all_falsified,
)


class TestRankHypotheses:
    def test_empty_list(self):
        assert rank_hypotheses([]) == []

    def test_ranks_by_stability_score_descending(self):
        hypotheses = [
            {"claim": "a", "geometric_stability_score": 0.5, "confidence_score": 0.9},
            {"claim": "b", "geometric_stability_score": 0.9, "confidence_score": 0.5},
            {"claim": "c", "geometric_stability_score": 0.7, "confidence_score": 0.7},
        ]
        ranked = rank_hypotheses(hypotheses)
        assert ranked[0]["claim"] == "b"
        assert ranked[1]["claim"] == "c"
        assert ranked[2]["claim"] == "a"

    def test_tiebreaker_by_confidence(self):
        hypotheses = [
            {"claim": "a", "geometric_stability_score": 0.8, "confidence_score": 0.5},
            {"claim": "b", "geometric_stability_score": 0.8, "confidence_score": 0.9},
        ]
        ranked = rank_hypotheses(hypotheses)
        assert ranked[0]["claim"] == "b"

    def test_stable_ranking(self):
        hypotheses = [
            {"claim": "x", "geometric_stability_score": 0.9, "confidence_score": 0.9},
            {"claim": "y", "geometric_stability_score": 0.1, "confidence_score": 0.1},
        ]
        for _ in range(50):
            ranked = rank_hypotheses(hypotheses)
            assert ranked[0]["claim"] == "x"


class TestValidateHypothesis:
    def test_empty_conditions_returns_inconclusive(self):
        assert validate_hypothesis({"testable_conditions": []}, {}) == "inconclusive"
        assert validate_hypothesis({}, {}) == "inconclusive"

    def test_eq_validated(self):
        hypothesis = {"testable_conditions": [{"field": "status", "operator": "eq", "value": "running"}]}
        assert validate_hypothesis(hypothesis, {"status": "running"}) == "validated"

    def test_eq_falsified(self):
        hypothesis = {"testable_conditions": [{"field": "status", "operator": "eq", "value": "running"}]}
        assert validate_hypothesis(hypothesis, {"status": "stopped"}) == "falsified"

    def test_gt_validated(self):
        hypothesis = {"testable_conditions": [{"field": "cpu", "operator": "gt", "value": 50}]}
        assert validate_hypothesis(hypothesis, {"cpu": 80}) == "validated"

    def test_gt_falsified(self):
        hypothesis = {"testable_conditions": [{"field": "cpu", "operator": "gt", "value": 50}]}
        assert validate_hypothesis(hypothesis, {"cpu": 30}) == "falsified"

    def test_lt_validated(self):
        hypothesis = {"testable_conditions": [{"field": "mem", "operator": "lt", "value": 90}]}
        assert validate_hypothesis(hypothesis, {"mem": 50}) == "validated"

    def test_gte_validated(self):
        hypothesis = {"testable_conditions": [{"field": "count", "operator": "gte", "value": 3}]}
        assert validate_hypothesis(hypothesis, {"count": 3}) == "validated"

    def test_lte_validated(self):
        hypothesis = {"testable_conditions": [{"field": "errors", "operator": "lte", "value": 0}]}
        assert validate_hypothesis(hypothesis, {"errors": 0}) == "validated"

    def test_contains_validated(self):
        hypothesis = {"testable_conditions": [{"field": "log", "operator": "contains", "value": "ERROR"}]}
        assert validate_hypothesis(hypothesis, {"log": "some ERROR occurred"}) == "validated"

    def test_contains_falsified(self):
        hypothesis = {"testable_conditions": [{"field": "log", "operator": "contains", "value": "ERROR"}]}
        assert validate_hypothesis(hypothesis, {"log": "all clear"}) == "falsified"

    def test_matches_regex(self):
        hypothesis = {"testable_conditions": [{"field": "name", "operator": "matches", "value": r"^pod-\d+$"}]}
        assert validate_hypothesis(hypothesis, {"name": "pod-123"}) == "validated"
        assert validate_hypothesis(hypothesis, {"name": "service-abc"}) == "falsified"

    def test_missing_field_inconclusive(self):
        hypothesis = {"testable_conditions": [{"field": "missing", "operator": "eq", "value": "x"}]}
        assert validate_hypothesis(hypothesis, {}) == "inconclusive"

    def test_multiple_conditions_all_pass(self):
        hypothesis = {
            "testable_conditions": [
                {"field": "status", "operator": "eq", "value": "running"},
                {"field": "cpu", "operator": "lt", "value": 90},
            ]
        }
        assert validate_hypothesis(hypothesis, {"status": "running", "cpu": 50}) == "validated"

    def test_multiple_conditions_one_fails(self):
        hypothesis = {
            "testable_conditions": [
                {"field": "status", "operator": "eq", "value": "running"},
                {"field": "cpu", "operator": "lt", "value": 90},
            ]
        }
        assert validate_hypothesis(hypothesis, {"status": "stopped", "cpu": 50}) == "falsified"

    def test_unknown_operator_inconclusive(self):
        hypothesis = {"testable_conditions": [{"field": "x", "operator": "xor", "value": 1}]}
        assert validate_hypothesis(hypothesis, {"x": 1}) == "inconclusive"

    def test_deterministic_validation(self):
        hypothesis = {"testable_conditions": [{"field": "val", "operator": "eq", "value": 42}]}
        evidence = {"val": 42}
        for _ in range(100):
            assert validate_hypothesis(hypothesis, evidence) == "validated"


class TestParseHypotheses:
    def test_parse_json_array(self):
        content = json.dumps([
            {"claim": "pod is down", "testable_conditions": [{"field": "status", "operator": "eq", "value": "down"}], "confidence_score": 0.8}
        ])
        result = _parse_hypotheses(content)
        assert len(result) == 1
        assert result[0]["claim"] == "pod is down"

    def test_parse_json_with_code_fence(self):
        content = '```json\n[{"claim": "test", "testable_conditions": [], "confidence_score": 0.5}]\n```'
        result = _parse_hypotheses(content)
        assert len(result) == 1

    def test_parse_dict_with_hypotheses_key(self):
        content = json.dumps({"hypotheses": [
            {"claim": "c1", "testable_conditions": [], "confidence_score": 0.6}
        ]})
        result = _parse_hypotheses(content)
        assert len(result) == 1

    def test_parse_single_dict(self):
        content = json.dumps({"claim": "solo", "testable_conditions": [], "confidence_score": 0.7})
        result = _parse_hypotheses(content)
        assert len(result) == 1
        assert result[0]["claim"] == "solo"

    def test_parse_invalid_json_returns_empty(self):
        result = _parse_hypotheses("not json at all")
        assert result == []

    def test_parse_empty_string_returns_empty(self):
        result = _parse_hypotheses("")
        assert result == []

    def test_filters_non_dict_items(self):
        content = json.dumps([{"claim": "valid", "testable_conditions": []}, "not a dict", 42])
        result = _parse_hypotheses(content)
        assert len(result) == 1


class TestNormalizeHypothesis:
    def test_extracts_required_fields(self):
        h = {"claim": "test", "testable_conditions": [{"field": "a", "operator": "eq", "value": 1}], "confidence_score": 0.9}
        result = _normalize_hypothesis(h)
        assert result["claim"] == "test"
        assert len(result["testable_conditions"]) == 1
        assert result["confidence_score"] == 0.9

    def test_handles_missing_claim(self):
        result = _normalize_hypothesis({})
        assert result["claim"] == ""
        assert result["confidence_score"] == 0.5

    def test_filters_invalid_conditions(self):
        h = {
            "claim": "test",
            "testable_conditions": [
                {"field": "a", "operator": "eq", "value": 1},
                {"invalid": "no field or operator"},
                {"field": "b"},
            ],
        }
        result = _normalize_hypothesis(h)
        assert len(result["testable_conditions"]) == 1

    def test_uses_confidence_fallback(self):
        h = {"claim": "t", "confidence": 0.75}
        result = _normalize_hypothesis(h)
        assert result["confidence_score"] == 0.75
