"""Evidence-based constraint classification engine.

Classifies system state by evaluating structured evidence against formal
constraint definitions. Classification is deterministic given the evidence.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.classification")


def classify_evidence(request: dict, db: Session) -> dict:
    """Classify an evidence bundle against all applicable constraints.

    Returns classification results with confidence scores and evidence chains.
    """
    bundle_id = request.get("evidence_bundle_id", str(uuid.uuid4()))
    evidence = request.get("evidence", {})
    constraint_ids = request.get("constraint_ids")

    audit_record = repository.create_audit_event(
        db,
        source_component="classification-engine",
        event_type="classification.started",
        payload_reference=bundle_id,
    )

    stage = request.get("stage")
    schema_version = request.get("schema_version")

    constraints = repository.get_constraint_definitions(db, stage=stage)
    if not constraints:
        from constraints.loader import sync_constraints_to_db
        sync_constraints_to_db(db)
        constraints = repository.get_constraint_definitions(db, stage=stage)

    if constraint_ids:
        constraints = [c for c in constraints if c.constraint_id in constraint_ids]

    if schema_version:
        mismatched = [c for c in constraints if c.version != schema_version]
        if mismatched:
            return {
                "error": "schema_version_mismatch",
                "expected_version": schema_version,
                "mismatched_constraints": [c.constraint_id for c in mismatched],
            }

    results = []
    for constraint in constraints:
        result = evaluate_constraint(constraint, evidence)
        classification = repository.create_classification(
            db,
            evidence_bundle_id=bundle_id,
            constraint_id=constraint.constraint_id,
            result=result["result"],
            confidence_score=result["confidence_score"],
            geometric_stability_score=result.get("geometric_stability_score"),
            geometric_stability_state=result.get("geometric_stability_state"),
            evidence_chain=result["evidence_chain"],
            llm_interpretation_used=result.get("llm_interpretation_used", False),
            audit_record_id=audit_record.event_id,
        )
        results.append({
            "classification_id": classification.classification_id,
            "constraint_id": constraint.constraint_id,
            **result,
        })

    db.commit()

    from events.publishers import publish_classification_completed
    publish_classification_completed({
        "evidence_bundle_id": bundle_id,
        "results": results,
        "audit_record_id": audit_record.event_id,
    })

    overall = _determine_overall_result(results)
    return {
        "classification_id": str(uuid.uuid4()),
        "evidence_bundle_id": bundle_id,
        "results": results,
        "overall_result": overall,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def evaluate_constraint(constraint, evidence: dict) -> dict:
    """Evaluate a single constraint against evidence.

    Returns result (pass/fail/inconclusive/unclassifiable), confidence,
    and evidence chain.
    """
    requirements = constraint.evidence_requirements or []
    missing_fields = [r for r in requirements if r not in evidence]

    if missing_fields:
        return {
            "result": "inconclusive",
            "confidence_score": 0.0,
            "evidence_chain": {"missing_fields": missing_fields},
            "llm_interpretation_used": False,
        }

    assertion_def = constraint.assertion_definition or {}
    assertion_type = constraint.assertion_type.value if constraint.assertion_type else "boolean"

    if assertion_type == "threshold":
        return _evaluate_threshold(assertion_def, evidence)
    elif assertion_type == "boolean":
        return _evaluate_boolean(assertion_def, evidence)
    elif assertion_type == "range":
        return _evaluate_range(assertion_def, evidence)
    elif assertion_type == "pattern":
        return _evaluate_pattern(assertion_def, evidence)
    elif assertion_type == "composite":
        return _evaluate_composite(assertion_def, evidence)
    elif assertion_type == "semantic":
        return _evaluate_semantic(assertion_def, evidence)
    else:
        return {
            "result": "unclassifiable",
            "confidence_score": 0.0,
            "evidence_chain": {"error": f"Unknown assertion type: {assertion_type}"},
            "llm_interpretation_used": False,
        }


def _evaluate_threshold(definition: dict, evidence: dict) -> dict:
    field = definition.get("field", "")
    operator = definition.get("operator", "gte")
    threshold = definition.get("value", 0)
    actual = evidence.get(field)

    if actual is None:
        return {"result": "inconclusive", "confidence_score": 0.0, "evidence_chain": {"field": field, "status": "missing"}, "llm_interpretation_used": False}

    ops = {"gt": actual > threshold, "gte": actual >= threshold, "lt": actual < threshold, "lte": actual <= threshold, "eq": actual == threshold}
    passed = ops.get(operator, False)
    return {
        "result": "pass" if passed else "fail",
        "confidence_score": 1.0,
        "evidence_chain": {"field": field, "actual": actual, "operator": operator, "threshold": threshold, "passed": passed},
        "llm_interpretation_used": False,
    }


def _evaluate_boolean(definition: dict, evidence: dict) -> dict:
    field = definition.get("field", "")
    expected = definition.get("value", True)
    actual = evidence.get(field)

    if actual is None:
        return {"result": "inconclusive", "confidence_score": 0.0, "evidence_chain": {"field": field, "status": "missing"}, "llm_interpretation_used": False}

    if isinstance(expected, bool):
        passed = bool(actual) == expected
    else:
        passed = str(actual) == str(expected)
    return {
        "result": "pass" if passed else "fail",
        "confidence_score": 1.0,
        "evidence_chain": {"field": field, "actual": actual, "expected": expected, "passed": passed},
        "llm_interpretation_used": False,
    }


def _evaluate_range(definition: dict, evidence: dict) -> dict:
    field = definition.get("field", "")
    min_val = definition.get("min")
    max_val = definition.get("max")
    actual = evidence.get(field)

    if actual is None:
        return {"result": "inconclusive", "confidence_score": 0.0, "evidence_chain": {"field": field, "status": "missing"}, "llm_interpretation_used": False}

    in_range = True
    if min_val is not None and actual < min_val:
        in_range = False
    if max_val is not None and actual > max_val:
        in_range = False

    return {
        "result": "pass" if in_range else "fail",
        "confidence_score": 1.0,
        "evidence_chain": {"field": field, "actual": actual, "min": min_val, "max": max_val, "in_range": in_range},
        "llm_interpretation_used": False,
    }


def _evaluate_pattern(definition: dict, evidence: dict) -> dict:
    field = definition.get("field", "")
    pattern = definition.get("pattern", "")
    actual = evidence.get(field)

    if actual is None:
        return {"result": "inconclusive", "confidence_score": 0.0, "evidence_chain": {"field": field, "status": "missing"}, "llm_interpretation_used": False}

    matched = bool(re.search(pattern, str(actual)))
    return {
        "result": "pass" if matched else "fail",
        "confidence_score": 1.0,
        "evidence_chain": {"field": field, "actual": str(actual), "pattern": pattern, "matched": matched},
        "llm_interpretation_used": False,
    }


def _evaluate_composite(definition: dict, evidence: dict) -> dict:
    sub_assertions = definition.get("assertions", [])
    logic = definition.get("logic", "all")

    sub_results = []
    for sub in sub_assertions:
        sub_type = sub.get("type", "boolean")
        if sub_type == "threshold":
            sub_results.append(_evaluate_threshold(sub, evidence))
        elif sub_type == "boolean":
            sub_results.append(_evaluate_boolean(sub, evidence))
        elif sub_type == "range":
            sub_results.append(_evaluate_range(sub, evidence))
        elif sub_type == "pattern":
            sub_results.append(_evaluate_pattern(sub, evidence))

    passes = [r["result"] == "pass" for r in sub_results]

    if logic == "all":
        passed = all(passes)
    elif logic == "any":
        passed = any(passes)
    else:
        passed = all(passes)

    confidence = sum(r["confidence_score"] for r in sub_results) / max(len(sub_results), 1)
    return {
        "result": "pass" if passed else "fail",
        "confidence_score": confidence,
        "evidence_chain": {"logic": logic, "sub_results": sub_results},
        "llm_interpretation_used": False,
    }


def _evaluate_semantic(definition: dict, evidence: dict) -> dict:
    """Use stability-aware LLM to interpret unstructured evidence."""
    import json
    question = definition.get("question", "Does this evidence indicate a problem?")
    field = definition.get("field", "")
    actual = evidence.get(field) if field else evidence

    try:
        from api.stability.wrapper import StabilityAwareLLMClient
        from api.routers._shared import STABILITY_THRESHOLD

        client = StabilityAwareLLMClient(stability_threshold=STABILITY_THRESHOLD)
        result = client.call(
            endpoint="semantic_classification",
            messages=[
                {"role": "system", "content": "You are a system state evaluator. Respond with JSON: {\"result\": \"pass\" or \"fail\", \"reasoning\": \"...\"}"},
                {"role": "user", "content": f"Question: {question}\nEvidence: {json.dumps(actual, default=str)}"},
            ],
            max_tokens=300,
            temperature=0.1,
        )

        if not result["success"]:
            return {
                "result": "inconclusive",
                "confidence_score": 0.0,
                "evidence_chain": {"error": "LLM call failed", "detail": result.get("error", "")},
                "llm_interpretation_used": True,
                "geometric_stability_score": 0.0,
                "geometric_stability_state": "unstable_fail",
            }

        stability_score = result["stability_score"]
        stability_state = result["stability_state"]

        try:
            parsed = json.loads(result["content"])
            llm_result = parsed.get("result", "inconclusive")
            if llm_result not in ("pass", "fail"):
                llm_result = "inconclusive"
        except (json.JSONDecodeError, ValueError):
            llm_result = "inconclusive"

        if stability_state in ("unstable_pass", "unstable_fail"):
            return {
                "result": "inconclusive",
                "confidence_score": stability_score,
                "evidence_chain": {
                    "llm_result": llm_result,
                    "stability_state": stability_state,
                    "note": "Unstable LLM interpretation — requires human review",
                },
                "llm_interpretation_used": True,
                "geometric_stability_score": stability_score,
                "geometric_stability_state": stability_state,
            }

        return {
            "result": llm_result,
            "confidence_score": stability_score,
            "evidence_chain": {"llm_result": llm_result, "stability_state": stability_state},
            "llm_interpretation_used": True,
            "geometric_stability_score": stability_score,
            "geometric_stability_state": stability_state,
        }

    except ImportError:
        return {
            "result": "inconclusive",
            "confidence_score": 0.0,
            "evidence_chain": {"note": "LLM client not available"},
            "llm_interpretation_used": True,
        }


def compute_confidence(evidence_completeness: float, assertion_strength: float, geometric_stability: float = 1.0, stability_weight: float = 0.5) -> float:
    base = (evidence_completeness + assertion_strength) / 2
    return base * (1 - stability_weight) + geometric_stability * stability_weight


def _determine_overall_result(results: list[dict]) -> str:
    result_values = [r["result"] for r in results]
    if "fail" in result_values:
        return "fail"
    if "unclassifiable" in result_values:
        return "unclassifiable"
    if "inconclusive" in result_values:
        return "inconclusive"
    return "pass"
