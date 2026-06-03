"""Deepfield router — task complexity to hardware substrate mapping.

Responds to computational irreducibility by acknowledging that each cluster
traces a unique irreducible trajectory requiring per-cluster calibration.
Uses geometric stability as a routing confidence signal.

Tiers:
  nano  → CPU   — deterministic, rule-based, boolean evaluation
  micro → Xeon6 — moderate reasoning, structured inference
  macro → Gaudi — complex reasoning, long context, multi-step inference
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db import repository
from db.models import TierAssignment, Substrate, StabilityState as DBStabilityState

logger = logging.getLogger("geolux.deepfield")

TIER_SUBSTRATE_MAP = {
    TierAssignment.NANO: Substrate.CPU,
    TierAssignment.MICRO: Substrate.XEON6,
    TierAssignment.MACRO: Substrate.GAUDI,
}

TIER_ESCALATION = {
    TierAssignment.NANO: TierAssignment.MICRO,
    TierAssignment.MICRO: TierAssignment.MACRO,
    TierAssignment.MACRO: TierAssignment.MACRO,
}

CLASSIFICATION_PROMPT = """You are a workload complexity classifier for infrastructure management.
Given a workload description, classify its complexity tier.

Tiers:
- nano: simple checks, boolean evaluation, no reasoning needed
- micro: moderate reasoning, pattern matching, structured classification
- macro: complex reasoning, novel analysis, cross-cluster correlation

Respond with JSON: {"tier": "nano|micro|macro", "reasoning": "...", "confidence": 0.0-1.0}"""


class DeepfieldRouter:
    def __init__(self):
        self._static_fallback = False

    def route(self, request: dict, db: Session) -> dict:
        """Route a workload to the appropriate hardware substrate."""
        workload_id = request.get("workload_id", str(uuid.uuid4()))
        workload_desc = request.get("workload_description", {})
        override_tier = request.get("override_tier")
        override_reason = request.get("override_reason")
        override_operator = request.get("override_operator")

        audit_record = repository.create_audit_event(
            db,
            source_component="deepfield",
            event_type="deepfield.routing.started",
            payload_reference=workload_id,
            operator=override_operator,
        )

        if override_tier:
            if not override_reason:
                return {"error": "override_reason required for manual routing"}
            tier = TierAssignment(override_tier)
            substrate = TIER_SUBSTRATE_MAP[tier]
            confidence = 1.0
            policy_rule = "operator_override"
            is_override = True
            stability_score = None
            stability_state = None
        else:
            tier, confidence, policy_rule, stability_score, stability_state = self.classify_workload(
                workload_desc, db
            )
            substrate = TIER_SUBSTRATE_MAP[tier]
            is_override = False

            if not self.check_availability(substrate):
                original_tier = tier
                tier, substrate = self._apply_fallback(tier)
                policy_rule = f"fallback_from_{original_tier.value}"
                logger.info("Substrate %s unavailable, falling back to %s", original_tier.value, tier.value)

        record = repository.create_routing_decision(
            db,
            workload_id=workload_id,
            workload_description=workload_desc,
            tier_assignment=tier,
            substrate=substrate,
            confidence_score=confidence,
            geometric_stability_score=stability_score,
            geometric_stability_state=stability_state,
            policy_rule_applied=policy_rule,
            override=is_override,
            override_reason=override_reason,
            override_operator=override_operator,
            audit_record_id=audit_record.event_id,
        )

        db.commit()

        result = {
            "routing_id": record.routing_id,
            "workload_id": workload_id,
            "tier_assignment": tier.value,
            "substrate": substrate.value,
            "confidence_score": confidence,
            "geometric_stability_score": stability_score,
            "geometric_stability_state": stability_state,
            "policy_rule_applied": policy_rule,
            "override": is_override,
            "created_at": record.created_at.isoformat(),
        }

        from events.publishers import publish_routing_decision
        publish_routing_decision(result)

        return result

    def classify_workload(self, description: dict, db: Optional[Session] = None) -> tuple:
        """Classify workload complexity to determine tier.

        Returns (tier, confidence, policy_rule, stability_score, stability_state).
        Uses LLM when available, falls back to rule-based classification.
        """
        if self._static_fallback:
            tier, confidence, rule = self._rule_based_classify(description)
            return tier, confidence, rule, None, None

        try:
            return self._llm_classify(description, db)
        except Exception as e:
            logger.warning("LLM classification failed, using rules: %s", e)
            tier, confidence, rule = self._rule_based_classify(description)
            return tier, confidence, rule, None, None

    def _llm_classify(self, description: dict, db: Optional[Session] = None) -> tuple:
        """Use stability-aware LLM for workload classification."""
        from api.stability.wrapper import StabilityAwareLLMClient

        threshold = float(os.environ.get("GEOLUX_STABILITY_THRESHOLD", "0.7"))
        client = StabilityAwareLLMClient(stability_threshold=threshold)

        result = client.call(
            endpoint="deepfield_classification",
            messages=[
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": json.dumps(description, default=str)},
            ],
            max_tokens=200,
            temperature=0.1,
            db=db,
        )

        if not result["success"]:
            tier, confidence, rule = self._rule_based_classify(description)
            return tier, confidence, rule, 0.0, "unstable_fail"

        stability_score = result["stability_score"]
        stability_state = result["stability_state"]

        if stability_state in ("unstable_pass", "unstable_fail"):
            tier, confidence, rule = self._rule_based_classify(description)
            tier = self._escalate_for_safety(tier)
            return tier, confidence * 0.5, f"unstable_{rule}", stability_score, stability_state

        try:
            parsed = json.loads(result["content"])
            tier_str = parsed.get("tier", "nano")
            tier = TierAssignment(tier_str)
            llm_confidence = parsed.get("confidence", 0.5)
            return tier, llm_confidence, "llm_classification", stability_score, stability_state
        except (json.JSONDecodeError, ValueError):
            tier, confidence, rule = self._rule_based_classify(description)
            return tier, confidence, rule, stability_score, stability_state

    def _rule_based_classify(self, description: dict) -> tuple:
        """Deterministic rule-based workload classification."""
        task_type = description.get("task_type", "")
        reasoning_required = description.get("reasoning_required", False)
        multi_step = description.get("multi_step", False)
        novel = description.get("novel", False)
        context_length = description.get("context_length", 0)

        if novel or (multi_step and reasoning_required) or context_length > 4096:
            return TierAssignment.MACRO, 0.8, "complexity_macro"

        if reasoning_required or multi_step or context_length > 1024:
            return TierAssignment.MICRO, 0.85, "complexity_micro"

        return TierAssignment.NANO, 0.95, "complexity_nano"

    def _escalate_for_safety(self, tier: TierAssignment) -> TierAssignment:
        """Escalate to next tier when classification is unstable."""
        return TIER_ESCALATION.get(tier, tier)

    def _apply_fallback(self, tier: TierAssignment) -> tuple:
        """Apply fallback when target substrate is unavailable."""
        escalated = TIER_ESCALATION.get(tier, tier)
        if escalated == tier:
            return TierAssignment.NANO, Substrate.CPU
        substrate = TIER_SUBSTRATE_MAP[escalated]
        if self.check_availability(substrate):
            return escalated, substrate
        return TierAssignment.NANO, Substrate.CPU

    def check_availability(self, substrate: Substrate) -> bool:
        """Check if target substrate is available."""
        if substrate == Substrate.GAUDI:
            return bool(os.environ.get("GEOLUX_GAUDI_URL"))
        elif substrate == Substrate.XEON6:
            return bool(os.environ.get("GEOLUX_XEON6_URL"))
        return True

    def suspend_adaptive_routing(self):
        """Suspend adaptive routing, fall back to static policy."""
        self._static_fallback = True
        logger.warning("Adaptive routing suspended — falling back to static rules")

    def resume_adaptive_routing(self):
        """Resume adaptive routing with LLM classification."""
        self._static_fallback = False
        logger.info("Adaptive routing resumed")
