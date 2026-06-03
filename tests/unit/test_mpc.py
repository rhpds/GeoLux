"""Unit tests for LLM-MPC controller."""

from __future__ import annotations

import pytest

from engine.mpc import MPCController


class TestMPCHorizonAdjustment:
    def setup_method(self):
        self.controller = MPCController(default_horizon=2, max_horizon=5)

    def test_no_scores_keeps_horizon(self):
        assert self.controller.adjust_horizon([], 2) == 2

    def test_stable_but_not_enough_to_extend(self):
        scores = [0.72, 0.74]
        assert self.controller.adjust_horizon(scores, 2) == 2

    def test_shortens_on_instability(self):
        scores = [0.5, 0.3, 0.6]
        result = self.controller.adjust_horizon(scores, 3)
        assert result == 2

    def test_minimum_is_one(self):
        scores = [0.1]
        assert self.controller.adjust_horizon(scores, 1) == 1

    def test_extends_on_sustained_stability(self):
        scores = [0.9, 0.85, 0.88]
        assert self.controller.adjust_horizon(scores, 2) == 3

    def test_never_exceeds_max(self):
        scores = [0.95, 0.95, 0.95]
        assert self.controller.adjust_horizon(scores, 5) == 5


class TestMPCOptimize:
    def setup_method(self):
        self.controller = MPCController(default_horizon=2, max_horizon=5)

    def test_empty_candidates_returns_none(self):
        action, score = self.controller.optimize([], [], {})
        assert action is None
        assert score == 0.0

    def test_returns_best_candidate_by_score(self):
        candidates = [
            {"action_id": "a", "score": 0.5},
            {"action_id": "b", "score": 0.9},
            {"action_id": "c", "score": 0.7},
        ]
        action, score = self.controller.optimize([], candidates, {})
        assert action["action_id"] == "b"


class TestMPCActivationGate:
    def test_gate_requires_minimum_history(self):
        controller = MPCController(min_history_weeks=4)
        assert controller.min_history_weeks == 4


class TestMPCSuspension:
    def test_no_suspension_with_stable_scores(self):
        controller = MPCController()
        assert controller._check_suspension([0.9, 0.85]) is False

    def test_suspension_after_consecutive_instabilities(self):
        controller = MPCController()
        controller._suspension_threshold = 3
        controller._check_suspension([0.3])
        controller._check_suspension([0.2])
        result = controller._check_suspension([0.1])
        assert result is True

    def test_instability_counter_resets_on_stable(self):
        controller = MPCController()
        controller._check_suspension([0.3])
        controller._check_suspension([0.2])
        controller._check_suspension([0.9])
        result = controller._check_suspension([0.3])
        assert result is False


class TestMPCGenerateCandidates:
    def test_generates_scale_candidate(self):
        controller = MPCController()
        candidates = controller._generate_candidates({}, {"type": "scale", "target": 5})
        assert len(candidates) == 1
        assert candidates[0]["action_type"] == "scale_replicas"

    def test_generates_remediate_candidate(self):
        controller = MPCController()
        candidates = controller._generate_candidates({}, {"type": "remediate", "remediation_id": "r1"})
        assert len(candidates) == 1
        assert candidates[0]["action_type"] == "execute_remediation"

    def test_generates_no_action_for_empty_objective(self):
        controller = MPCController()
        candidates = controller._generate_candidates({}, {})
        assert len(candidates) == 1
        assert candidates[0]["action_type"] == "no_action"


class TestMPCHorizonInvariants:
    def test_horizon_always_in_valid_range(self):
        controller = MPCController(default_horizon=2, max_horizon=5)
        import random
        for _ in range(100):
            scores = [random.random() for _ in range(random.randint(0, 10))]
            horizon = random.randint(1, 5)
            result = controller.adjust_horizon(scores, horizon)
            assert 1 <= result <= 5
