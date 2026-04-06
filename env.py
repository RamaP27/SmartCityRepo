import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and ALL models so metadata is populated
from shems.database import Base  # noqa: E402
from shems.domains.auth.models import User, Session  # noqa: E402, F401
from shems.domains.household.models import Household, Device, EnergyReading, DeviceSchedule  # noqa: E402, F401
from shems.domains.sustainability.models import CarbonScore, SustainabilityBenchmark, CarbonOffsetGoal  # noqa: E402, F401
from shems.domains.billing.models import BillingAccount, SpendingCap, OverageAlert, UsageSummary  # noqa: E402, F401
from shems.domains.tariff.models import TariffZone, RateWindow  # noqa: E402, F401
from shems.domains.grid.models import GridZone, GridLoadReading, DemandForecast, AnomalyAlert, DemandResponseEvent  # noqa: E402, F401

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
