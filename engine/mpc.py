"""LLM-MPC (Model Predictive Control) controller.

Applies model predictive control theory to agent decision-making using
LLM reasoning over system state as the dynamics model. Responds to
computational irreducibility by using short receding horizons calibrated
to locally smooth dynamics.

Control loop:
1. Maintain state model from evidence collectors
2. Generate predictions over receding horizon N using LLM
3. Optimize control action against predictions within constraints
4. Execute first action only
5. Observe outcome, update state, replan
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

logger = logging.getLogger("geolux.mpc")

PREDICTION_SYSTEM_PROMPT = """You are a system state predictor for infrastructure management.
Given current system state and a prediction horizon, predict the system state
at each future step.

Respond with JSON: {"predictions": [{"step": 1, "predicted_state": {...}, "confidence": 0.0-1.0}, ...]}
Each predicted_state should include the same fields as the input state with projected values."""

ACTION_SCORING_PROMPT = """You are a control action optimizer for infrastructure management.
Given predicted state trajectory and candidate actions, score each action
on how well it achieves the objective.

Respond with JSON: {"scores": [{"action_id": "...", "score": 0.0-1.0, "reasoning": "..."}, ...]}"""


def get_stability_threshold() -> float:
    return float(os.environ.get("GEOLUX_STABILITY_THRESHOLD", "0.7"))


def get_mpc_config() -> dict:
    return {
        "default_horizon": int(os.environ.get("GEOLUX_MPC_HORIZON", "2")),
        "max_horizon": int(os.environ.get("GEOLUX_MPC_MAX_HORIZON", "5")),
        "min_history_weeks": int(os.environ.get("GEOLUX_MPC_MIN_HISTORY_WEEKS", "4")),
    }


class MPCController:
    def __init__(
        self,
        default_horizon: int = 2,
        max_horizon: int = 5,
        min_history_weeks: int = 4,
    ):
        self.default_horizon = default_horizon
        self.max_horizon = max_horizon
        self.min_history_weeks = min_history_weeks
        self._consecutive_instabilities = 0
        self._suspension_threshold = 3

    def plan(self, request: dict, db: Session) -> dict:
        """Execute one MPC planning cycle."""
        cluster_id = request["cluster_id"]
        current_state = request["current_state"]
        objective = request.get("objective", {})
        requested_horizon = request.get("horizon") or self.default_horizon
        horizon = min(requested_horizon, self.max_horizon)

        if not self.check_activation_gate(cluster_id, db):
            return {
                "error": "MPC not activated — insufficient operational history",
                "cluster_id": cluster_id,
                "required_history_weeks": self.min_history_weeks,
                "suspended": False,
            }

        audit_record = repository.create_audit_event(
            db,
            source_component="llm-mpc",
            event_type="mpc.cycle.started",
            payload_reference=cluster_id,
        )

        predictions, stability_scores = self.predict(current_state, horizon, db)
        horizon = self.adjust_horizon(stability_scores, horizon)

        suspended = self._check_suspension(stability_scores)
        if suspended:
            repository.create_audit_event(
                db,
                source_component="llm-mpc",
                event_type="mpc.suspended",
                payload_reference=cluster_id,
            )

        candidate_actions = self._generate_candidates(current_state, objective)

        selected_action = None
        optimization_score = 0.0
        if not suspended and candidate_actions and predictions:
            selected_action, optimization_score = self.optimize(
                predictions, candidate_actions, objective, db
            )

        stability_profile = {
            "scores": stability_scores,
            "mean": sum(stability_scores) / max(len(stability_scores), 1),
            "min": min(stability_scores) if stability_scores else 0.0,
        }

        cycle = repository.create_mpc_cycle(
            db,
            cluster_id=cluster_id,
            horizon=horizon,
            current_state=current_state,
            predictions=predictions,
            candidate_actions=candidate_actions,
            selected_action_id=selected_action.get("action_id") if selected_action else None,
            optimization_score=optimization_score,
            geometric_stability_profile=stability_profile,
            horizon_adjusted=horizon != requested_horizon,
            suspended=suspended,
            audit_record_id=audit_record.event_id,
        )

        db.commit()

        from events.publishers import publish_mpc_action_recommended
        publish_mpc_action_recommended({
            "cycle_id": cycle.cycle_id,
            "cluster_id": cluster_id,
            "recommended_action": selected_action,
            "horizon": horizon,
            "suspended": suspended,
        })

        return {
            "cycle_id": cycle.cycle_id,
            "cluster_id": cluster_id,
            "horizon": horizon,
            "predictions": predictions,
            "recommended_action": selected_action,
            "optimization_score": optimization_score,
            "geometric_stability_profile": stability_profile,
            "horizon_adjusted": horizon != requested_horizon,
            "suspended": suspended,
            "created_at": cycle.created_at.isoformat(),
        }

    def predict(self, state: dict, horizon: int, db: Optional[Session] = None) -> tuple[list[dict], list[float]]:
        """Generate predictions over the receding horizon using LLM."""
        stability_scores = []
        try:
            from api.stability.wrapper import StabilityAwareLLMClient
            client = StabilityAwareLLMClient(stability_threshold=get_stability_threshold())

            result = client.call(
                endpoint="mpc_prediction",
                messages=[
                    {"role": "system", "content": PREDICTION_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({
                        "current_state": state,
                        "horizon": horizon,
                    }, default=str)},
                ],
                max_tokens=800,
                temperature=0.2,
                db=db,
            )

            stability_scores.append(result["stability_score"])

            if not result["success"]:
                return [], stability_scores

            try:
                parsed = json.loads(result["content"])
                predictions = parsed.get("predictions", [])
                return predictions, stability_scores
            except (json.JSONDecodeError, ValueError):
                return [], stability_scores

        except Exception as e:
            logger.warning("MPC prediction failed: %s", e)
            return [], [0.0]

    def optimize(
        self,
        predictions: list[dict],
        candidates: list[dict],
        objective: dict,
        db: Optional[Session] = None,
    ) -> tuple[Optional[dict], float]:
        """Select highest-scoring candidate action within constraint boundaries."""
        if not candidates:
            return None, 0.0

        scored = self._score_candidates(predictions, candidates, objective, db)
        if not scored:
            return max(candidates, key=lambda c: c.get("score", 0.0)), 0.0

        best = max(scored, key=lambda s: s.get("score", 0.0))
        action = next((c for c in candidates if c.get("action_id") == best.get("action_id")), candidates[0])
        return action, best.get("score", 0.0)

    def _score_candidates(
        self,
        predictions: list[dict],
        candidates: list[dict],
        objective: dict,
        db: Optional[Session] = None,
    ) -> list[dict]:
        """Score candidates using LLM against predicted trajectory."""
        try:
            from api.stability.wrapper import StabilityAwareLLMClient
            client = StabilityAwareLLMClient(stability_threshold=get_stability_threshold())

            result = client.call(
                endpoint="mpc_optimization",
                messages=[
                    {"role": "system", "content": ACTION_SCORING_PROMPT},
                    {"role": "user", "content": json.dumps({
                        "predictions": predictions,
                        "candidates": candidates,
                        "objective": objective,
                    }, default=str)},
                ],
                max_tokens=500,
                temperature=0.1,
                db=db,
            )

            if not result["success"]:
                return []

            parsed = json.loads(result["content"])
            return parsed.get("scores", [])
        except Exception:
            return []

    def adjust_horizon(self, stability_scores: list[float], current_horizon: int) -> int:
        """Adjust horizon based on geometric stability.

        Shortens when stability falls below threshold.
        Extends only when sustained stability is observed.
        """
        if not stability_scores:
            return current_horizon

        threshold = get_stability_threshold()
        mean_stability = sum(stability_scores) / len(stability_scores)
        min_stability = min(stability_scores)

        if min_stability < threshold:
            return max(1, current_horizon - 1)

        if mean_stability > threshold + 0.1 and len(stability_scores) >= 3:
            if all(s > threshold for s in stability_scores[-3:]):
                return min(current_horizon + 1, self.max_horizon)

        return current_horizon

    def check_activation_gate(self, cluster_id: str, db: Session) -> bool:
        """MPC must not activate until cluster has sufficient operational history.

        Checks the glx_classifications table for evaluation records from
        the cluster. Requires min_history_weeks worth of data.
        """
        from db.models import ClassificationRecord
        from datetime import timedelta

        query = db.query(ClassificationRecord).filter(
            ClassificationRecord.evidence_bundle_id.like(f"%{cluster_id}%"),
        )

        if self.min_history_weeks > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(weeks=self.min_history_weeks)
            try:
                query = query.filter(ClassificationRecord.created_at >= cutoff)
            except Exception:
                pass

        return query.count() >= 10

    def _check_suspension(self, stability_scores: list[float]) -> bool:
        """Check if MPC should be suspended due to sustained instability."""
        threshold = get_stability_threshold()

        if stability_scores and min(stability_scores) < threshold:
            self._consecutive_instabilities += 1
        else:
            self._consecutive_instabilities = 0

        if self._consecutive_instabilities >= self._suspension_threshold:
            logger.warning("MPC suspended — %d consecutive instabilities", self._consecutive_instabilities)
            return True

        return False

    def _generate_candidates(self, state: dict, objective: dict) -> list[dict]:
        """Generate candidate control actions from current state and objective."""
        candidates = []

        if objective.get("type") == "scale":
            candidates.append({
                "action_id": str(uuid.uuid4()),
                "action_type": "scale_replicas",
                "parameters": {"target_replicas": objective.get("target", 3)},
                "score": 0.0,
            })

        if objective.get("type") == "remediate":
            candidates.append({
                "action_id": str(uuid.uuid4()),
                "action_type": "execute_remediation",
                "parameters": {"remediation_id": objective.get("remediation_id", "")},
                "score": 0.0,
            })

        if not candidates:
            candidates.append({
                "action_id": str(uuid.uuid4()),
                "action_type": "no_action",
                "parameters": {},
                "score": 0.5,
            })

        return candidates
