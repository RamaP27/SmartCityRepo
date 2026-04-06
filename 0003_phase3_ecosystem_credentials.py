"""Phase 3 — add ecosystem_credentials to households.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "households",
        sa.Column("ecosystem_credentials", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("households", "ecosystem_credentials")
