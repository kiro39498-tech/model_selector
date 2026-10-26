"""create orchestrator_runs table

Revision ID: 0003_orchestrator_runs
Revises: 0002_bigint_params
Create Date: 2026-10-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_orchestrator_runs"
down_revision = "0002_bigint_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orchestrator_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=True),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_orchestrator_runs_status", "orchestrator_runs", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_orchestrator_runs_status", table_name="orchestrator_runs")
    op.drop_table("orchestrator_runs")
