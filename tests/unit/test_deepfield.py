"""Unit tests for Deepfield router."""

from __future__ import annotations

import pytest

from engine.deepfield import DeepfieldRouter, TIER_SUBSTRATE_MAP, TIER_ESCALATION
from db.models import TierAssignment, Substrate


class TestRuleBasedClassification:
    def setup_method(self):
        self.router = DeepfieldRouter()

    def test_simple_task_routes_to_nano(self):
        desc = {"task_type": "check_pod_status", "reasoning_required": False, "multi_step": False, "novel": False}
        tier, confidence, rule = self.router._rule_based_classify(desc)
        assert tier == TierAssignment.NANO
        assert confidence >= 0.9

    def test_moderate_task_routes_to_micro(self):
        desc = {"task_type": "classify_failure", "reasoning_required": True, "multi_step": False, "novel": False}
        tier, confidence, rule = self.router._rule_based_classify(desc)
        assert tier == TierAssignment.MICRO

    def test_complex_task_routes_to_macro(self):
        desc = {"task_type": "root_cause_analysis", "reasoning_required": True, "multi_step": True, "novel": True}
        tier, confidence, rule = self.router._rule_based_classify(desc)
        assert tier == TierAssignment.MACRO

    def test_long_context_routes_to_macro(self):
        desc = {"task_type": "analysis", "context_length": 8192}
        tier, _, _ = self.router._rule_based_classify(desc)
        assert tier == TierAssignment.MACRO

    def test_medium_context_routes_to_micro(self):
        desc = {"task_type": "analysis", "context_length": 2048}
        tier, _, _ = self.router._rule_based_classify(desc)
        assert tier == TierAssignment.MICRO

    def test_empty_description_routes_to_nano(self):
        tier, _, _ = self.router._rule_based_classify({})
        assert tier == TierAssignment.NANO


class TestTierMappings:
    def test_tier_substrate_map(self):
        assert TIER_SUBSTRATE_MAP[TierAssignment.NANO] == Substrate.CPU
        assert TIER_SUBSTRATE_MAP[TierAssignment.MICRO] == Substrate.XEON6
        assert TIER_SUBSTRATE_MAP[TierAssignment.MACRO] == Substrate.GAUDI

    def test_tier_escalation_map(self):
        assert TIER_ESCALATION[TierAssignment.NANO] == TierAssignment.MICRO
        assert TIER_ESCALATION[TierAssignment.MICRO] == TierAssignment.MACRO
        assert TIER_ESCALATION[TierAssignment.MACRO] == TierAssignment.MACRO


class TestEscalation:
    def test_escalate_nano_to_micro(self):
        router = DeepfieldRouter()
        assert router._escalate_for_safety(TierAssignment.NANO) == TierAssignment.MICRO

    def test_escalate_micro_to_macro(self):
        router = DeepfieldRouter()
        assert router._escalate_for_safety(TierAssignment.MICRO) == TierAssignment.MACRO

    def test_escalate_macro_stays_macro(self):
        router = DeepfieldRouter()
        assert router._escalate_for_safety(TierAssignment.MACRO) == TierAssignment.MACRO


class TestFallback:
    def test_fallback_nano_when_nothing_available(self):
        router = DeepfieldRouter()
        tier, substrate = router._apply_fallback(TierAssignment.MACRO)
        assert substrate == Substrate.CPU

    def test_cpu_always_available(self):
        router = DeepfieldRouter()
        assert router.check_availability(Substrate.CPU) is True


class TestAdaptiveRoutingSuspension:
    def test_suspend_sets_static_fallback(self):
        router = DeepfieldRouter()
        router.suspend_adaptive_routing()
        assert router._static_fallback is True

    def test_resume_clears_static_fallback(self):
        router = DeepfieldRouter()
        router.suspend_adaptive_routing()
        router.resume_adaptive_routing()
        assert router._static_fallback is False

    def test_static_fallback_uses_rules(self):
        router = DeepfieldRouter()
        router.suspend_adaptive_routing()
        tier, confidence, rule, stab_score, stab_state = router.classify_workload(
            {"task_type": "complex", "novel": True}
        )
        assert tier == TierAssignment.MACRO
        assert stab_score is None

    def test_override_requires_reason(self):
        router = DeepfieldRouter()

        class FakeDB:
            def add(self, *a): pass
            def flush(self): pass
            def commit(self): pass
            def query(self, *a): return self
            def filter(self, *a): return self
            def order_by(self, *a): return self
            def limit(self, *a): return self
            def all(self): return []

        result = router.route({
            "workload_id": "w1",
            "workload_description": {},
            "override_tier": "macro",
        }, FakeDB())
        assert "error" in result
        assert "override_reason" in result["error"]
