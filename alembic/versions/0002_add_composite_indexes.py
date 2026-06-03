"""Add composite indexes for common query patterns.

Revision ID: 0002_composite_idx
Revises: 0001_geolux_init
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_composite_idx"
down_revision: Union[str, None] = "0001_geolux_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_glx_hyp_bundle_outcome", "glx_hypotheses", ["evidence_bundle_id", "validation_outcome"])
    op.create_index("idx_glx_cls_bundle_result", "glx_classifications", ["evidence_bundle_id", "result"])
    op.create_index("idx_glx_mpc_cluster_time", "glx_mpc_cycles", ["cluster_id", "created_at"])
    op.create_index("idx_glx_route_tier_time", "glx_routing_decisions", ["tier_assignment", "created_at"])
    op.create_index("idx_glx_stab_endpoint_time", "glx_llm_stability_records", ["endpoint", "created_at"])
    op.create_index("idx_glx_audit_source_type_time", "glx_audit_events", ["source_component", "event_type", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_glx_audit_source_type_time")
    op.drop_index("idx_glx_stab_endpoint_time")
    op.drop_index("idx_glx_route_tier_time")
    op.drop_index("idx_glx_mpc_cluster_time")
    op.drop_index("idx_glx_cls_bundle_result")
    op.drop_index("idx_glx_hyp_bundle_outcome")
