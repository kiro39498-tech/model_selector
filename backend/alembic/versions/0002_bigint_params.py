"""alter model_registry param columns to bigint

Revision ID: 0002_bigint_params
Revises: 0001_initial
Create Date: 2026-10-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_bigint_params"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Parameter counts (e.g. 27B = 27_000_000_000) exceed the 32-bit INTEGER
    # range. Widen both columns to BIGINT. Nullability, defaults, indexes,
    # and existing data are preserved (ALTER TYPE does not drop data).
    op.alter_column(
        "model_registry",
        "total_params",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "model_registry",
        "active_params",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Revert to INTEGER. NOTE: any existing value above the 32-bit range
    # (2,147,483,647) would overflow on downgrade; this is only safe when no
    # such rows exist.
    op.alter_column(
        "model_registry",
        "total_params",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "model_registry",
        "active_params",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
