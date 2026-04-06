"""Initial schema — all tables + TimescaleDB hypertables

Revision ID: 0001
Revises:
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── TimescaleDB extension ────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # ── ENUM types ───────────────────────────────────────────────────────────
    persona_type = postgresql.ENUM("HOMEOWNER", "RENTER", "GRID_MANAGER", name="personatype")
    persona_type.create(op.get_bind())

    ecosystem_type = postgresql.ENUM(
        "GOOGLE_HOME", "APPLE_HOMEKIT", "ZIGBEE", "MANUAL", name="ecosystemtype"
    )
    ecosystem_type.create(op.get_bind())

    device_type = postgresql.ENUM(
        "EV_CHARGER", "HVAC", "WASHER", "DRYER", "DISHWASHER",
        "LIGHTING", "REFRIGERATOR", "WATER_HEATER", "OTHER",
        name="devicetype",
    )
    device_type.create(op.get_bind())

    schedule_type = postgresql.ENUM(
        "OFF_PEAK_AUTO", "MANUAL", "AI_SUGGESTED", name="scheduletype"
    )
    schedule_type.create(op.get_bind())

    reading_source = postgresql.ENUM(
        "SMART_METER", "DEVICE_API", "MANUAL_ENTRY", name="readingsource"
    )
    reading_source.create(op.get_bind())

    window_type = postgresql.ENUM("PEAK", "OFF_PEAK", "SUPER_OFF_PEAK", name="windowtype")
    window_type.create(op.get_bind())

    alert_type = postgresql.ENUM(
        "WARNING_THRESHOLD", "CAP_REACHED", "PEAK_SPIKE", name="alerttype"
    )
    alert_type.create(op.get_bind())

    notification_channel = postgresql.ENUM("PUSH", "SMS", "EMAIL", name="notificationchannel")
    notification_channel.create(op.get_bind())

    goal_status = postgresql.ENUM("ACTIVE", "ACHIEVED", "MISSED", name="goalstatus")
    goal_status.create(op.get_bind())

    grid_load_source = postgresql.ENUM("SCADA", "SYNTHETIC", "ESTIMATED", name="gridloadsource")
    grid_load_source.create(op.get_bind())

    anomaly_type = postgresql.ENUM(
        "CONSUMPTION_SPIKE", "METER_FAULT", "UNUSUAL_PATTERN", "GRID_STRESS",
        name="anomalytype",
    )
    anomaly_type.create(op.get_bind())

    alert_severity = postgresql.ENUM("LOW", "MEDIUM", "HIGH", "CRITICAL", name="alertseverity")
    alert_severity.create(op.get_bind())

    dr_trigger_type = postgresql.ENUM(
        "MANUAL", "AUTOMATED_ML", "SCHEDULED", name="drtriggertype"
    )
    dr_trigger_type.create(op.get_bind())

    dr_status = postgresql.ENUM(
        "PENDING", "ACTIVE", "COMPLETED", "CANCELLED", name="drstatus"
    )
    dr_status.create(op.get_bind())

    # ── AUTH ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("persona_type", sa.Enum("HOMEOWNER", "RENTER", "GRID_MANAGER", name="personatype"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("refresh_token_hash", sa.String(255), nullable=True),
        sa.Column("device_fingerprint", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])
    op.create_index("ix_sessions_refresh_token_hash", "sessions", ["refresh_token_hash"])

    # ── GRID ZONES (must exist before households FK) ─────────────────────────
    op.create_table(
        "grid_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_name", sa.String(100), nullable=False),
        sa.Column("district_code", sa.String(20), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("total_households", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("peak_capacity_kw", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_grid_zones_district_code", "grid_zones", ["district_code"])

    # ── TARIFF ───────────────────────────────────────────────────────────────
    op.create_table(
        "tariff_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("zone_name", sa.String(100), nullable=False),
        sa.Column("utility_provider", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "rate_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tariff_zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tariff_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_type", sa.Enum("PEAK", "OFF_PEAK", "SUPER_OFF_PEAK", name="windowtype"), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("days_of_week", postgresql.JSON(), nullable=False),
        sa.Column("rate_per_kwh", sa.Float(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rate_windows_tariff_zone_id", "rate_windows", ["tariff_zone_id"])

    # ── HOUSEHOLD ─────────────────────────────────────────────────────────────
    op.create_table(
        "households",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address_hash", sa.String(64), nullable=False),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("smart_meter_id", sa.String(100), nullable=True),
        sa.Column("ecosystem_type", sa.Enum("GOOGLE_HOME", "APPLE_HOMEKIT", "ZIGBEE", "MANUAL", name="ecosystemtype"), nullable=False, server_default="MANUAL"),
        sa.Column("square_footage", sa.Integer(), nullable=True),
        sa.Column("occupant_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_households_user_id", "households", ["user_id"])
    op.create_index("ix_households_smart_meter_id", "households", ["smart_meter_id"])

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_device_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("device_type", sa.Enum("EV_CHARGER", "HVAC", "WASHER", "DRYER", "DISHWASHER", "LIGHTING", "REFRIGERATOR", "WATER_HEATER", "OTHER", name="devicetype"), nullable=False),
        sa.Column("rated_power_watts", sa.Float(), nullable=True),
        sa.Column("is_schedulable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("ecosystem", sa.Enum("GOOGLE_HOME", "APPLE_HOMEKIT", "ZIGBEE", "MANUAL", name="ecosystemtype"), nullable=False, server_default="MANUAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_devices_household_id", "devices", ["household_id"])

    # ── ENERGY READINGS (TimescaleDB hypertable) ──────────────────────────────
    op.create_table(
        "energy_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumption_kwh", sa.Float(), nullable=False),
        sa.Column("cost_estimate_inr", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_peak_hour", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source", sa.Enum("SMART_METER", "DEVICE_API", "MANUAL_ENTRY", name="readingsource"), nullable=False, server_default="SMART_METER"),
    )
    op.create_index("ix_energy_readings_household_id", "energy_readings", ["household_id"])
    op.create_index("ix_energy_readings_device_id", "energy_readings", ["device_id"])
    op.create_index("ix_energy_readings_timestamp", "energy_readings", ["timestamp"])

    # Convert to TimescaleDB hypertable (partition by timestamp, 1-day chunks)
    op.execute(
        "SELECT create_hypertable('energy_readings', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);"
    )

    op.create_table(
        "device_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_type", sa.Enum("OFF_PEAK_AUTO", "MANUAL", "AI_SUGGESTED", name="scheduletype"), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("days_of_week", postgresql.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_ai", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_device_schedules_device_id", "device_schedules", ["device_id"])

    # ── SUSTAINABILITY ────────────────────────────────────────────────────────
    op.create_table(
        "carbon_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_kwh", sa.Float(), nullable=False),
        sa.Column("carbon_kg_co2e", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("percentile_rank", sa.Float(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_carbon_scores_household_id", "carbon_scores", ["household_id"])

    op.create_table(
        "sustainability_benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("avg_consumption_kwh", sa.Float(), nullable=False),
        sa.Column("median_carbon_kg", sa.Float(), nullable=False),
        sa.Column("top_10pct_threshold_kwh", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sustainability_benchmarks_district_id", "sustainability_benchmarks", ["district_id"])

    op.create_table(
        "carbon_offset_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_reduction_pct", sa.Float(), nullable=False),
        sa.Column("baseline_carbon_kg", sa.Float(), nullable=False),
        sa.Column("target_carbon_kg", sa.Float(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("current_progress_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("ACTIVE", "ACHIEVED", "MISSED", name="goalstatus"), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_carbon_offset_goals_household_id", "carbon_offset_goals", ["household_id"])

    # ── BILLING ───────────────────────────────────────────────────────────────
    op.create_table(
        "billing_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tariff_zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tariff_zones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("utility_provider", sa.String(100), nullable=False),
        sa.Column("meter_reference", sa.String(100), nullable=True),
        sa.Column("billing_cycle_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_billing_accounts_user_id", "billing_accounts", ["user_id"])

    op.create_table(
        "spending_caps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("billing_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("billing_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monthly_cap_inr", sa.Float(), nullable=False),
        sa.Column("warning_threshold_pct", sa.Float(), nullable=False, server_default="80"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_spending_caps_billing_account_id", "spending_caps", ["billing_account_id"])

    op.create_table(
        "overage_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("billing_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("billing_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", sa.Enum("WARNING_THRESHOLD", "CAP_REACHED", "PEAK_SPIKE", name="alerttype"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_spend_inr", sa.Float(), nullable=False),
        sa.Column("cap_inr", sa.Float(), nullable=False),
        sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("channel", sa.Enum("PUSH", "SMS", "EMAIL", name="notificationchannel"), nullable=False, server_default="PUSH"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_overage_alerts_billing_account_id", "overage_alerts", ["billing_account_id"])

    op.create_table(
        "usage_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("billing_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("billing_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("total_kwh", sa.Float(), nullable=False, server_default="0"),
        sa.Column("peak_kwh", sa.Float(), nullable=False, server_default="0"),
        sa.Column("off_peak_kwh", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_inr", sa.Float(), nullable=False, server_default="0"),
        sa.Column("potential_savings_inr", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_summaries_billing_account_id", "usage_summaries", ["billing_account_id"])
    op.create_index("ix_usage_summaries_period_date", "usage_summaries", ["period_date"])

    # ── GRID LOAD READINGS (TimescaleDB hypertable) ───────────────────────────
    op.create_table(
        "grid_load_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_load_kw", sa.Float(), nullable=False),
        sa.Column("capacity_utilization_pct", sa.Float(), nullable=False),
        sa.Column("source", sa.Enum("SCADA", "SYNTHETIC", "ESTIMATED", name="gridloadsource"), nullable=False, server_default="SCADA"),
    )
    op.create_index("ix_grid_load_readings_zone_id", "grid_load_readings", ["zone_id"])
    op.create_index("ix_grid_load_readings_timestamp", "grid_load_readings", ["timestamp"])

    op.execute(
        "SELECT create_hypertable('grid_load_readings', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);"
    )

    # ── REMAINING GRID TABLES ─────────────────────────────────────────────────
    op.create_table(
        "demand_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forecast_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_hours", sa.Integer(), nullable=False),
        sa.Column("predicted_load_kw", sa.Float(), nullable=False),
        sa.Column("confidence_lower", sa.Float(), nullable=False),
        sa.Column("confidence_upper", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False, server_default="v1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_demand_forecasts_zone_id", "demand_forecasts", ["zone_id"])

    op.create_table(
        "anomaly_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="SET NULL"), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anomaly_type", sa.Enum("CONSUMPTION_SPIKE", "METER_FAULT", "UNUSUAL_PATTERN", "GRID_STRESS", name="anomalytype"), nullable=False),
        sa.Column("severity", sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="alertseverity"), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_anomaly_alerts_zone_id", "anomaly_alerts", ["zone_id"])
    op.create_index("ix_anomaly_alerts_household_id", "anomaly_alerts", ["household_id"])

    op.create_table(
        "demand_response_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grid_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trigger_type", sa.Enum("MANUAL", "AUTOMATED_ML", "SCHEDULED", name="drtriggertype"), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "ACTIVE", "COMPLETED", "CANCELLED", name="drstatus"), nullable=False, server_default="PENDING"),
        sa.Column("target_load_reduction_kw", sa.Float(), nullable=False),
        sa.Column("actual_load_reduction_kw", sa.Float(), nullable=True),
        sa.Column("households_targeted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incentive_offer_inr", sa.Float(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_demand_response_events_zone_id", "demand_response_events", ["zone_id"])


def downgrade() -> None:
    op.drop_table("demand_response_events")
    op.drop_table("anomaly_alerts")
    op.drop_table("demand_forecasts")
    op.drop_table("grid_load_readings")
    op.drop_table("usage_summaries")
    op.drop_table("overage_alerts")
    op.drop_table("spending_caps")
    op.drop_table("billing_accounts")
    op.drop_table("carbon_offset_goals")
    op.drop_table("sustainability_benchmarks")
    op.drop_table("carbon_scores")
    op.drop_table("device_schedules")
    op.drop_table("energy_readings")
    op.drop_table("devices")
    op.drop_table("households")
    op.drop_table("rate_windows")
    op.drop_table("tariff_zones")
    op.drop_table("grid_zones")
    op.drop_table("sessions")
    op.drop_table("users")

    for enum_name in [
        "personatype", "ecosystemtype", "devicetype", "scheduletype", "readingsource",
        "windowtype", "alerttype", "notificationchannel", "goalstatus",
        "gridloadsource", "anomalytype", "alertseverity", "drtriggertype", "drstatus",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")

    op.execute("DROP EXTENSION IF EXISTS timescaledb;")
