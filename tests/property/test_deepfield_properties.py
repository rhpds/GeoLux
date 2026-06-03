"""Property-based tests for Deepfield router."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from engine.deepfield import DeepfieldRouter, TIER_SUBSTRATE_MAP
from db.models import TierAssignment, Substrate


workload_desc = st.fixed_dictionaries({
    "task_type": st.text(min_size=0, max_size=20),
    "reasoning_required": st.booleans(),
    "multi_step": st.booleans(),
    "novel": st.booleans(),
    "context_length": st.integers(min_value=0, max_value=16384),
})


class TestClassificationInvariants:
    @given(desc=workload_desc)
    @settings(max_examples=300)
    def test_classification_always_returns_valid_tier(self, desc):
        router = DeepfieldRouter()
        tier, confidence, rule = router._rule_based_classify(desc)
        assert tier in (TierAssignment.NANO, TierAssignment.MICRO, TierAssignment.MACRO)
        assert 0.0 <= confidence <= 1.0
        assert len(rule) > 0

    @given(desc=workload_desc)
    @settings(max_examples=200)
    def test_classification_is_deterministic(self, desc):
        router = DeepfieldRouter()
        r1 = router._rule_based_classify(desc)
        r2 = router._rule_based_classify(desc)
        assert r1 == r2

    @given(desc=workload_desc)
    @settings(max_examples=200)
    def test_tier_always_has_substrate_mapping(self, desc):
        router = DeepfieldRouter()
        tier, _, _ = router._rule_based_classify(desc)
        assert tier in TIER_SUBSTRATE_MAP


class TestEscalationInvariants:
    @given(tier=st.sampled_from(list(TierAssignment)))
    @settings(max_examples=50)
    def test_escalation_never_downgrades(self, tier):
        router = DeepfieldRouter()
        escalated = router._escalate_for_safety(tier)
        tier_order = {TierAssignment.NANO: 0, TierAssignment.MICRO: 1, TierAssignment.MACRO: 2}
        assert tier_order[escalated] >= tier_order[tier]

    @given(tier=st.sampled_from(list(TierAssignment)))
    @settings(max_examples=50)
    def test_escalation_is_idempotent_at_max(self, tier):
        router = DeepfieldRouter()
        e1 = router._escalate_for_safety(tier)
        e2 = router._escalate_for_safety(e1)
        e3 = router._escalate_for_safety(e2)
        assert e2 == e3


class TestFallbackInvariants:
    @given(tier=st.sampled_from(list(TierAssignment)))
    @settings(max_examples=50)
    def test_fallback_always_returns_valid_tier_and_substrate(self, tier):
        router = DeepfieldRouter()
        fb_tier, fb_substrate = router._apply_fallback(tier)
        assert fb_tier in TierAssignment
        assert fb_substrate in Substrate
