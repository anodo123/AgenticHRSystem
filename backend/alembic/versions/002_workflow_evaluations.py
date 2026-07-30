"""Add persisted workflow evaluations.

Revision ID: 002_workflow_evaluations
Revises: 001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "002_workflow_evaluations"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "workflow_evaluations" in inspector.get_table_names():
        return
    op.create_table(
        "workflow_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("final_state", sa.String(length=50), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("agent_success_rate", sa.Float(), nullable=False),
        sa.Column("compliance_decision", sa.String(length=50), nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.UniqueConstraint("evaluation_id"),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_index("ix_workflow_evaluations_id", "workflow_evaluations", ["id"])
    op.create_index(
        "ix_workflow_evaluations_evaluation_id",
        "workflow_evaluations", ["evaluation_id"], unique=True,
    )
    op.create_index(
        "ix_workflow_evaluations_workflow_id",
        "workflow_evaluations", ["workflow_id"], unique=True,
    )
    op.create_index(
        "ix_workflow_evaluations_final_state",
        "workflow_evaluations", ["final_state"],
    )
    op.create_index(
        "ix_workflow_evaluations_compliance_decision",
        "workflow_evaluations", ["compliance_decision"],
    )
    op.create_index(
        "ix_workflow_evaluations_evaluated_at",
        "workflow_evaluations", ["evaluated_at"],
    )


def downgrade() -> None:
    op.drop_table("workflow_evaluations")
