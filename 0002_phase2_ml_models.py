"""Phase 2 — update sustainability models, add CANCELLED goal status.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old sustainability tables (stub schema replaced with Phase 2 design)
    op.drop_table("sustainability_benchmarks")
    op.drop_table("carbon_offset_goals")
    op.drop_table("carbon_scores")

    # Drop old enum if it exists
    op.execute("DROP TYPE IF EXISTS goalstatus CASCADE")

    # Create new goalstatus enum with CANCELLED
    op.execute(
        "CREATE TYPE goalstatus AS ENUM ('ACTIVE', 'ACHIEVED', 'MISSED', 'CANCELLED')"
    )

    # Recreate carbon_scores with Phase 2 schema
    op.create_table(
        "carbon_scores",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_kwh", sa.Float, nullable=False),
        sa.Column("carbon_kg", sa.Float, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("grade", sa.String(3), nullable=False),
        sa.Column("percentile_rank", sa.Float, nullable=False, server_default="0"),
        sa.Column("cluster_key", sa.String(30), nullable=False, server_default=""),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_carbon_scores_household_id", "carbon_scores", ["household_id"])

    # Recreate sustainability_benchmarks with cluster_key design
    op.create_table(
        "sustainability_benchmarks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cluster_key", sa.String(30), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("median_kwh", sa.Float, nullable=False),
        sa.Column("p75_kwh", sa.Float, nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_sustainability_benchmarks_cluster_key",
        "sustainability_benchmarks",
        ["cluster_key"],
    )

    # Recreate carbon_offset_goals with Phase 2 schema
    op.create_table(
        "carbon_offset_goals",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_reduction_pct", sa.Float, nullable=False),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_monthly_kwh", sa.Float, nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "ACHIEVED", "MISSED", "CANCELLED", name="goalstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_carbon_offset_goals_household_id",
        "carbon_offset_goals",
        ["household_id"],
    )


def downgrade() -> None:
    op.drop_table("carbon_offset_goals")
    op.drop_table("sustainability_benchmarks")
    op.drop_table("carbon_scores")
    op.execute("DROP TYPE IF EXISTS goalstatus CASCADE")
