"""Hypothesis Engine (THE) — core logic.

Generates structured falsifiable hypotheses about observed system state.
Responds to computational irreducibility by replacing prediction with
structured falsifiable inquiry.

The LLM generates hypotheses; a separate deterministic mechanism validates
them. The LLM's confidence is irrelevant — only evidence validation matters.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db import repository
from db.models import StabilityMethod as DBStabilityMethod, StabilityState as DBStabilityState

logger = logging.getLogger("geolux.hypothesis")

HYPOTHESIS_SYSTEM_PROMPT = """You are a hypothesis generator for infrastructure state analysis.
Given an evidence bundle describing cluster/namespace state, generate structured
falsifiable hypotheses about the observed conditions.

Each hypothesis must have:
- claim: a specific falsifiable statement about the system state
- testable_conditions: an array of conditions that can be checked against evidence
  Each condition has: field (evidence field name), operator (eq/gt/lt/gte/lte/contains/matches), value
- confidence_score: your confidence in this hypothesis (0.0 to 1.0)

The evidence may include cross-system context under the "cross_system" key:
- stargate: recent rubric evaluation results, failure classes, pass rates
- deepfield: cluster signal patterns, RCA categories, incident history
- launchpad: provisioning intelligence, routing patterns

Use cross-system data to generate hypotheses that span system boundaries.
For example: "If StarGate shows repeated deployment-ready failures AND DeepField
shows recurring pod_crashloop signals, the root cause may be systemic."

Respond ONLY with a JSON array of hypothesis objects. No other text."""


def generate_hypotheses(
    evidence_bundle: dict,
    db: Session,
    stability_threshold: Optional[float] = None,
) -> dict:
    """Generate ranked hypothesis queue from an evidence bundle.

    High geometric stability hypotheses generated first. If stability falls
    below threshold, generation is skipped and an instability event is logged.
    If LLM is unavailable, last known hypotheses are queued with staleness flag.
    """
    from api.routers._shared import STABILITY_THRESHOLD
    threshold = stability_threshold or STABILITY_THRESHOLD

    bundle_id = evidence_bundle.get("bundle_id", str(uuid.uuid4()))
    evidence_fields = evidence_bundle.get("evidence_fields", evidence_bundle)

    # Enrich with cross-system data
    try:
        from engine.evidence_enricher import EvidenceEnricher
        enricher = EvidenceEnricher(db)
        evidence_bundle = enricher.enrich(evidence_bundle)
        evidence_fields = evidence_bundle.get("evidence_fields", evidence_fields)
    except Exception as e:
        logger.debug("Evidence enrichment failed (non-critical): %s", e)

    audit_record = repository.create_audit_event(
        db,
        source_component="hypothesis-engine",
        event_type="hypothesis.generation.started",
        payload_reference=bundle_id,
    )

    llm_result = _call_llm_for_hypotheses(evidence_fields, threshold, db)

    if llm_result["gated"]:
        repository.create_audit_event(
            db,
            source_component="hypothesis-engine",
            event_type="hypothesis.generation.gated",
            payload_reference=bundle_id,
            geometric_stability_score=llm_result.get("stability_score", 0.0),
        )
        db.commit()

        from events.publishers import publish_audit_event
        publish_audit_event({
            "source_component": "hypothesis-engine",
            "event_type": "stability.threshold.breach",
            "bundle_id": bundle_id,
            "stability_score": llm_result.get("stability_score", 0.0),
        })

        return {
            "evidence_bundle_id": bundle_id,
            "hypotheses": [],
            "total": 0,
            "gated": True,
            "reason": "Geometric instability — generation suspended",
            "stability_score": llm_result.get("stability_score", 0.0),
            "audit_record_id": audit_record.event_id,
        }

    if llm_result["unavailable"]:
        stale_hypotheses = _get_stale_hypotheses(bundle_id, db)
        return {
            "evidence_bundle_id": bundle_id,
            "hypotheses": stale_hypotheses,
            "total": len(stale_hypotheses),
            "stale": True,
            "reason": "LLM unavailable — returning last known hypotheses",
            "audit_record_id": audit_record.event_id,
        }

    raw_hypotheses = llm_result["hypotheses"]
    stability_score = llm_result["stability_score"]
    stability_state = llm_result["stability_state"]
    stability_method = llm_result["stability_method"]

    persisted = []
    for h in raw_hypotheses:
        method_enum = _resolve_stability_method(stability_method)
        state_enum = _resolve_stability_state(stability_state)

        record = repository.create_hypothesis(
            db,
            evidence_bundle_id=bundle_id,
            claim=h.get("claim", ""),
            testable_conditions=h.get("testable_conditions", []),
            confidence_score=h.get("confidence_score", 0.0),
            geometric_stability_score=stability_score,
            geometric_stability_method=method_enum,
            geometric_stability_state=state_enum,
            evidence_snapshot=evidence_fields,
            audit_record_id=audit_record.event_id,
        )
        persisted.append({
            "hypothesis_id": record.hypothesis_id,
            "claim": record.claim,
            "testable_conditions": record.testable_conditions,
            "confidence_score": record.confidence_score,
            "geometric_stability_score": record.geometric_stability_score,
            "geometric_stability_state": stability_state,
            "created_at": record.created_at.isoformat(),
        })

    ranked = rank_hypotheses(persisted)
    db.commit()

    from events.publishers import publish_hypothesis_generated
    for h in ranked:
        publish_hypothesis_generated(h)

    return {
        "evidence_bundle_id": bundle_id,
        "hypotheses": ranked,
        "total": len(ranked),
        "stability_score": stability_score,
        "stability_state": stability_state,
        "audit_record_id": audit_record.event_id,
    }


def _call_llm_for_hypotheses(evidence: dict, threshold: float, db: Session) -> dict:
    """Call stability-aware LLM to generate hypotheses."""
    try:
        from api.stability.wrapper import StabilityAwareLLMClient
        client = StabilityAwareLLMClient(stability_threshold=threshold)

        user_content = f"Generate hypotheses for the following evidence:\n{json.dumps(evidence, default=str)}"
        result = client.call(
            endpoint="hypothesis_generation",
            messages=[
                {"role": "system", "content": HYPOTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=1000,
            temperature=0.3,
            db=db,
        )

        if not result["success"]:
            return {"hypotheses": [], "unavailable": True, "gated": False}

        stability_score = result["stability_score"]
        if stability_score < threshold:
            return {
                "hypotheses": [],
                "gated": True,
                "unavailable": False,
                "stability_score": stability_score,
            }

        hypotheses = _parse_hypotheses(result["content"])
        return {
            "hypotheses": hypotheses,
            "stability_score": stability_score,
            "stability_state": result["stability_state"],
            "stability_method": result["stability_method"],
            "gated": False,
            "unavailable": False,
        }

    except Exception as e:
        logger.warning("LLM call failed for hypothesis generation: %s", e)
        return {"hypotheses": [], "unavailable": True, "gated": False}


def _parse_hypotheses(content: str) -> list[dict]:
    """Parse LLM output into structured hypothesis list."""
    try:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [_normalize_hypothesis(h) for h in parsed if isinstance(h, dict)]
        if isinstance(parsed, dict) and "hypotheses" in parsed:
            return [_normalize_hypothesis(h) for h in parsed["hypotheses"] if isinstance(h, dict)]
        if isinstance(parsed, dict):
            return [_normalize_hypothesis(parsed)]
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse hypothesis response: %s", e)
    return []


def _normalize_hypothesis(h: dict) -> dict:
    """Ensure hypothesis has required fields."""
    conditions = h.get("testable_conditions", [])
    if isinstance(conditions, list):
        conditions = [
            c for c in conditions
            if isinstance(c, dict) and "field" in c and "operator" in c
        ]

    return {
        "claim": str(h.get("claim", "")),
        "testable_conditions": conditions,
        "confidence_score": float(h.get("confidence_score", h.get("confidence", 0.5))),
    }


def _get_stale_hypotheses(bundle_id: str, db: Session) -> list[dict]:
    """Return last known hypotheses with staleness flag."""
    records = repository.get_hypothesis_queue(db, limit=10)
    return [
        {
            "hypothesis_id": r.hypothesis_id,
            "claim": r.claim,
            "testable_conditions": r.testable_conditions or [],
            "confidence_score": r.confidence_score,
            "geometric_stability_score": r.geometric_stability_score,
            "geometric_stability_state": r.geometric_stability_state.value if r.geometric_stability_state else "",
            "stale": True,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in records
    ]


def _resolve_stability_method(method_str: str) -> DBStabilityMethod:
    mapping = {
        "token_probability": DBStabilityMethod.TOKEN_PROBABILITY,
        "logit_entropy": DBStabilityMethod.LOGIT_ENTROPY,
        "perplexity": DBStabilityMethod.PERPLEXITY,
        "activation_variance": DBStabilityMethod.ACTIVATION_VARIANCE,
    }
    return mapping.get(method_str, DBStabilityMethod.TOKEN_PROBABILITY)


def _resolve_stability_state(state_str: str) -> DBStabilityState:
    mapping = {
        "stable_pass": DBStabilityState.STABLE_PASS,
        "unstable_pass": DBStabilityState.UNSTABLE_PASS,
        "stable_fail": DBStabilityState.STABLE_FAIL,
        "unstable_fail": DBStabilityState.UNSTABLE_FAIL,
    }
    return mapping.get(state_str, DBStabilityState.UNSTABLE_FAIL)


def rank_hypotheses(hypotheses: list[dict]) -> list[dict]:
    """Rank hypotheses by geometric stability score, then by prior validation rate."""
    return sorted(
        hypotheses,
        key=lambda h: (
            h.get("geometric_stability_score", 0.0),
            h.get("confidence_score", 0.0),
        ),
        reverse=True,
    )


def validate_hypothesis(hypothesis: dict, evidence: dict) -> str:
    """Validate a hypothesis against evidence deterministically.

    Returns: 'validated', 'falsified', or 'inconclusive'.
    The LLM's confidence is irrelevant — only evidence validation matters.
    """
    conditions = hypothesis.get("testable_conditions", [])
    if not conditions:
        return "inconclusive"

    results = []
    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        expected = condition.get("value")

        actual = evidence.get(field)
        if actual is None:
            results.append("inconclusive")
            continue

        try:
            if operator == "eq":
                results.append("validated" if actual == expected else "falsified")
            elif operator == "gt":
                results.append("validated" if float(actual) > float(expected) else "falsified")
            elif operator == "lt":
                results.append("validated" if float(actual) < float(expected) else "falsified")
            elif operator == "gte":
                results.append("validated" if float(actual) >= float(expected) else "falsified")
            elif operator == "lte":
                results.append("validated" if float(actual) <= float(expected) else "falsified")
            elif operator == "contains":
                results.append("validated" if expected in str(actual) else "falsified")
            elif operator == "matches":
                import re
                results.append("validated" if re.search(str(expected), str(actual)) else "falsified")
            else:
                results.append("inconclusive")
        except (TypeError, ValueError):
            results.append("inconclusive")

    if "falsified" in results:
        return "falsified"
    if all(r == "validated" for r in results):
        return "validated"
    return "inconclusive"


def check_all_falsified(bundle_id: str, db: Session) -> bool:
    """Check if all hypotheses for a bundle have been falsified.

    If true, triggers a rubric extension event for human review.
    """
    records = repository.get_hypotheses_for_bundle(db, bundle_id, limit=100)
    if not records:
        return False

    all_resolved = all(r.validation_outcome is not None for r in records)
    if not all_resolved:
        return False

    all_falsified = all(
        r.validation_outcome.value == "falsified"
        for r in records
        if r.validation_outcome is not None
    )

    if all_falsified:
        repository.create_audit_event(
            db,
            source_component="hypothesis-engine",
            event_type="hypothesis.all_falsified",
            payload_reference=bundle_id,
        )
        from events.publishers import publish_audit_event
        publish_audit_event({
            "source_component": "hypothesis-engine",
            "event_type": "rubric.extension.triggered",
            "bundle_id": bundle_id,
            "reason": "All hypotheses falsified — novel failure mode suspected",
        })
        db.commit()

    return all_falsified
