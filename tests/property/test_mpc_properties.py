"""Property-based tests for LLM-MPC controller."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from engine.mpc import MPCController


class TestHorizonInvariants:
    @given(
        scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=0,
            max_size=15,
        ),
        current=st.integers(min_value=1, max_value=10),
        max_h=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=500)
    def test_horizon_always_between_1_and_max(self, scores, current, max_h):
        controller = MPCController(max_horizon=max_h)
        current = min(current, max_h)
        result = controller.adjust_horizon(scores, current)
        assert 1 <= result <= max_h

    @given(
        scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=0,
            max_size=10,
        ),
        current=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=300)
    def test_horizon_adjustment_is_deterministic(self, scores, current):
        controller = MPCController(default_horizon=2, max_horizon=5)
        r1 = controller.adjust_horizon(scores, current)
        r2 = controller.adjust_horizon(scores, current)
        assert r1 == r2

    @given(
        scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=1,
            max_size=10,
        ),
        current=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=300)
    def test_horizon_changes_by_at_most_one(self, scores, current):
        controller = MPCController(default_horizon=2, max_horizon=5)
        current = min(current, 5)
        result = controller.adjust_horizon(scores, current)
        assert abs(result - current) <= 1


class TestSuspensionInvariants:
    @given(n=st.integers(min_value=1, max_value=20))
    @settings(max_examples=50)
    def test_suspension_triggers_at_threshold(self, n):
        controller = MPCController()
        controller._suspension_threshold = n
        for _ in range(n - 1):
            assert controller._check_suspension([0.1]) is False
        assert controller._check_suspension([0.1]) is True

    @given(
        unstable_count=st.integers(min_value=0, max_value=5),
        threshold=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_reset_on_stable_prevents_suspension(self, unstable_count, threshold):
        controller = MPCController()
        controller._suspension_threshold = threshold
        for _ in range(min(unstable_count, threshold - 1)):
            controller._check_suspension([0.1])
        controller._check_suspension([0.9])
        result = controller._check_suspension([0.1])
        assert result is False or threshold == 1
