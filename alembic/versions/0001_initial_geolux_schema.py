"""Initial GeoLux schema — all component tables.

Revision ID: 0001_geolux_init
Revises: None
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_geolux_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STABILITY_METHOD = sa.Enum("activation_variance", "token_probability", "perplexity", "logit_entropy", name="glx_stability_method")
STABILITY_STATE = sa.Enum("stable_pass", "unstable_pass", "stable_fail", "unstable_fail", name="glx_stability_state")
ASSERTION_TYPE = sa.Enum("threshold", "boolean", "range", "pattern", "composite", "semantic", name="glx_assertion_type")
SEVERITY = sa.Enum("critical", "major", "minor", name="glx_severity")
CLASSIFICATION_RESULT = sa.Enum("pass", "fail", "inconclusive", "unclassifiable", name="glx_classification_result")
TIER = sa.Enum("nano", "micro", "macro", name="glx_tier")
SUBSTRATE = sa.Enum("cpu", "xeon6", "gaudi", name="glx_substrate")
TRIGGER_TYPE = sa.Enum("auto", "manual", "system", name="glx_trigger_type")
VALIDATION_OUTCOME = sa.Enum("validated", "falsified", "inconclusive", name="glx_validation_outcome")


def upgrade() -> None:
    # ── Geometric Stability ───────────────────────────────────────
    op.create_table(
        "glx_llm_stability_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("endpoint", sa.String(100), nullable=False, index=True),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("stability_score", sa.Float(), nullable=False),
        sa.Column("stability_method", STABILITY_METHOD, nullable=False),
        sa.Column("stability_threshold", sa.Float(), nullable=False),
        sa.Column("stability_state", STABILITY_STATE, nullable=False),
        sa.Column("raw_signal", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── Hypothesis Engine ─────────────────────────────────────────
    op.create_table(
        "glx_hypotheses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hypothesis_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("evidence_bundle_id", sa.String(255), nullable=False, index=True),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("testable_conditions", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("geometric_stability_score", sa.Float(), nullable=False),
        sa.Column("geometric_stability_method", STABILITY_METHOD, nullable=False),
        sa.Column("geometric_stability_state", STABILITY_STATE, nullable=False),
        sa.Column("validation_outcome", VALIDATION_OUTCOME, nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_record_id", sa.String(255), nullable=True, index=True),
    )
    op.create_index("idx_glx_hyp_stability", "glx_hypotheses", ["geometric_stability_score"])
    op.create_index("idx_glx_hyp_validation", "glx_hypotheses", ["validation_outcome"])

    # ── Constraint Classification ─────────────────────────────────
    op.create_table(
        "glx_constraint_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("constraint_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("constraint_name", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False, index=True),
        sa.Column("assertion_type", ASSERTION_TYPE, nullable=False),
        sa.Column("assertion_definition", sa.JSON(), nullable=False),
        sa.Column("evidence_requirements", sa.JSON(), nullable=False),
        sa.Column("severity", SEVERITY, nullable=False),
        sa.Column("remediation_class", sa.String(255), nullable=True),
        sa.Column("geometric_stability_weight", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "glx_classifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("classification_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("evidence_bundle_id", sa.String(255), nullable=False, index=True),
        sa.Column("constraint_id", sa.String(255), nullable=False, index=True),
        sa.Column("result", CLASSIFICATION_RESULT, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("geometric_stability_score", sa.Float(), nullable=True),
        sa.Column("geometric_stability_state", STABILITY_STATE, nullable=True),
        sa.Column("evidence_chain", sa.JSON(), nullable=False),
        sa.Column("llm_interpretation_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_record_id", sa.String(255), nullable=True, index=True),
    )
    op.create_index("idx_glx_cls_constraint", "glx_classifications", ["constraint_id"])
    op.create_index("idx_glx_cls_result", "glx_classifications", ["result"])

    # ── LLM-MPC ───────────────────────────────────────────────────
    op.create_table(
        "glx_mpc_cycles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cycle_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("cluster_id", sa.String(255), nullable=False, index=True),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("current_state", sa.JSON(), nullable=False),
        sa.Column("predictions", sa.JSON(), nullable=False),
        sa.Column("candidate_actions", sa.JSON(), nullable=False),
        sa.Column("selected_action_id", sa.String(255), nullable=True),
        sa.Column("optimization_score", sa.Float(), nullable=True),
        sa.Column("geometric_stability_profile", sa.JSON(), nullable=False),
        sa.Column("horizon_adjusted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("suspended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_record_id", sa.String(255), nullable=True, index=True),
    )

    # ── Deepfield Routing ─────────────────────────────────────────
    op.create_table(
        "glx_routing_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("routing_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("workload_id", sa.String(255), nullable=False, index=True),
        sa.Column("workload_description", sa.JSON(), nullable=False),
        sa.Column("tier_assignment", TIER, nullable=False),
        sa.Column("substrate", SUBSTRATE, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("geometric_stability_score", sa.Float(), nullable=True),
        sa.Column("geometric_stability_state", STABILITY_STATE, nullable=True),
        sa.Column("policy_rule_applied", sa.String(255), nullable=True),
        sa.Column("override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("override_reason", sa.String(500), nullable=True),
        sa.Column("override_operator", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_record_id", sa.String(255), nullable=True, index=True),
    )
    op.create_index("idx_glx_route_tier", "glx_routing_decisions", ["tier_assignment"])
    op.create_index("idx_glx_route_substrate", "glx_routing_decisions", ["substrate"])

    # ── NanoObs ───────────────────────────────────────────────────
    op.create_table(
        "glx_nano_obs_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("observation_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("cluster_id", sa.String(255), nullable=False, index=True),
        sa.Column("agent_id", sa.String(255), nullable=False, index=True),
        sa.Column("threshold_id", sa.String(255), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("drift_detected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("drift_magnitude", sa.Float(), nullable=True),
        sa.Column("adjustment_recommended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("adjustment_value", sa.Float(), nullable=True),
        sa.Column("adjustment_approved", sa.Boolean(), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_glx_nobs_cluster_agent", "glx_nano_obs_records", ["cluster_id", "agent_id"])

    # ── Audit Events ──────────────────────────────────────────────
    op.create_table(
        "glx_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("source_component", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_reference", sa.String(255), nullable=True),
        sa.Column("geometric_stability_score", sa.Float(), nullable=True),
        sa.Column("operator", sa.String(255), nullable=True),
        sa.Column("trigger_type", TRIGGER_TYPE, nullable=False, server_default="auto"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_glx_audit_source", "glx_audit_events", ["source_component"])
    op.create_index("idx_glx_audit_type", "glx_audit_events", ["event_type"])

    # ── Launchpad Intelligence ────────────────────────────────────
    op.create_table(
        "glx_launchpad_intelligence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("intelligence_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("intelligence_type", sa.String(100), nullable=False, index=True),
        sa.Column("data_payload", sa.JSON(), nullable=False),
        sa.Column("time_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("glx_launchpad_intelligence")
    op.drop_table("glx_audit_events")
    op.drop_table("glx_nano_obs_records")
    op.drop_table("glx_routing_decisions")
    op.drop_table("glx_mpc_cycles")
    op.drop_table("glx_classifications")
    op.drop_table("glx_constraint_definitions")
    op.drop_table("glx_hypotheses")
    op.drop_table("glx_llm_stability_records")

    for enum_name in [
        "glx_validation_outcome", "glx_trigger_type", "glx_substrate", "glx_tier",
        "glx_classification_result", "glx_severity", "glx_assertion_type",
        "glx_stability_state", "glx_stability_method",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
