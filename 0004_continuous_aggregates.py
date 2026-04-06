"""Phase 4 — TimescaleDB continuous aggregates for hourly/daily rollups.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-23

Creates:
  - energy_readings_hourly  — hourly kWh rollup per household
  - energy_readings_daily   — daily  kWh rollup per household
  - grid_load_hourly        — hourly avg/max load per zone
  - grid_load_daily         — daily  avg/max load per zone

These are TimescaleDB continuous aggregates (materialized views with auto-refresh).
They power the dashboard endpoints without hitting raw hypertables.
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Household energy — hourly rollup ─────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS energy_readings_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', timestamp)   AS bucket,
            household_id,
            SUM(consumption_kwh)               AS total_kwh,
            AVG(consumption_kwh)               AS avg_kwh,
            COUNT(*)                           AS reading_count,
            BOOL_OR(is_peak_hour)              AS any_peak
        FROM energy_readings
        GROUP BY bucket, household_id
        WITH NO DATA;
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'energy_readings_hourly',
            start_offset => INTERVAL '3 days',
            end_offset   => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        );
    """)

    # ── Household energy — daily rollup ──────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS energy_readings_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', timestamp)    AS bucket,
            household_id,
            SUM(consumption_kwh)               AS total_kwh,
            SUM(CASE WHEN is_peak_hour THEN consumption_kwh ELSE 0 END)     AS peak_kwh,
            SUM(CASE WHEN NOT is_peak_hour THEN consumption_kwh ELSE 0 END) AS off_peak_kwh,
            COUNT(*)                           AS reading_count
        FROM energy_readings
        GROUP BY bucket, household_id
        WITH NO DATA;
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'energy_readings_daily',
            start_offset => INTERVAL '14 days',
            end_offset   => INTERVAL '1 day',
            schedule_interval => INTERVAL '6 hours'
        );
    """)

    # ── Grid load — hourly rollup ─────────────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS grid_load_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', timestamp)   AS bucket,
            zone_id,
            AVG(current_load_kw)               AS avg_load_kw,
            MAX(current_load_kw)               AS peak_load_kw,
            MIN(current_load_kw)               AS min_load_kw,
            AVG(capacity_utilization_pct)      AS avg_utilization_pct,
            MAX(capacity_utilization_pct)      AS max_utilization_pct
        FROM grid_load_readings
        GROUP BY bucket, zone_id
        WITH NO DATA;
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'grid_load_hourly',
            start_offset => INTERVAL '7 days',
            end_offset   => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        );
    """)

    # ── Grid load — daily rollup ──────────────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS grid_load_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', timestamp)    AS bucket,
            zone_id,
            AVG(current_load_kw)               AS avg_load_kw,
            MAX(current_load_kw)               AS peak_load_kw,
            MIN(current_load_kw)               AS min_load_kw,
            AVG(capacity_utilization_pct)      AS avg_utilization_pct
        FROM grid_load_readings
        GROUP BY bucket, zone_id
        WITH NO DATA;
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'grid_load_daily',
            start_offset => INTERVAL '90 days',
            end_offset   => INTERVAL '1 day',
            schedule_interval => INTERVAL '12 hours'
        );
    """)

    # Refresh all views now with available data
    op.execute("CALL refresh_continuous_aggregate('energy_readings_hourly', NULL, NULL);")
    op.execute("CALL refresh_continuous_aggregate('energy_readings_daily', NULL, NULL);")
    op.execute("CALL refresh_continuous_aggregate('grid_load_hourly', NULL, NULL);")
    op.execute("CALL refresh_continuous_aggregate('grid_load_daily', NULL, NULL);")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS grid_load_daily CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS grid_load_hourly CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS energy_readings_daily CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS energy_readings_hourly CASCADE;")
