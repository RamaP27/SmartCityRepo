"""
Synthetic data seed script for SHEMS development.

Generates:
  - 5 grid zones + tariff zones with rate windows
  - 50 households with realistic device sets
  - 1 year of 15-minute energy readings per household
  - 1 HOMEOWNER user (Sarah), 1 RENTER user (Marcus), 1 GRID_MANAGER user (Priya)

Usage:
    python scripts/seed_synthetic_data.py
    python scripts/seed_synthetic_data.py --households 20 --days 30
"""
import argparse
import asyncio
import hashlib
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone

from faker import Faker

fake = Faker("en_IN")
random.seed(42)

DISTRICTS = [
    {"name": "North Zone", "code": "NZ", "city": "Mumbai", "peak_kw": 45000.0},
    {"name": "South Zone", "code": "SZ", "city": "Mumbai", "peak_kw": 38000.0},
    {"name": "East Zone", "code": "EZ", "city": "Pune", "peak_kw": 29000.0},
    {"name": "West Zone", "code": "WZ", "city": "Pune", "peak_kw": 31000.0},
    {"name": "Central Zone", "code": "CZ", "city": "Bangalore", "peak_kw": 52000.0},
]

# Typical Indian ToU tariff rates (INR per kWh)
RATE_WINDOWS = [
    {"type": "PEAK", "start": time(6, 0), "end": time(10, 0), "rate": 9.50, "days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]},
    {"type": "PEAK", "start": time(18, 0), "end": time(22, 0), "rate": 9.50, "days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]},
    {"type": "OFF_PEAK", "start": time(10, 0), "end": time(18, 0), "rate": 6.50, "days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]},
    {"type": "SUPER_OFF_PEAK", "start": time(22, 0), "end": time(6, 0), "rate": 4.00, "days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]},
]

DEVICE_TEMPLATES = [
    {"name": "Air Conditioner", "type": "HVAC", "watts": 1500, "schedulable": True},
    {"name": "EV Charger", "type": "EV_CHARGER", "watts": 7400, "schedulable": True},
    {"name": "Washing Machine", "type": "WASHER", "watts": 500, "schedulable": True},
    {"name": "Dishwasher", "type": "DISHWASHER", "watts": 1200, "schedulable": True},
    {"name": "Refrigerator", "type": "REFRIGERATOR", "watts": 150, "schedulable": False},
    {"name": "Water Heater", "type": "WATER_HEATER", "watts": 2000, "schedulable": True},
    {"name": "Lighting", "type": "LIGHTING", "watts": 200, "schedulable": False},
]


def consumption_profile(hour: int, is_weekend: bool) -> float:
    """Return a consumption multiplier based on time of day and day type."""
    if is_weekend:
        profile = [0.3, 0.2, 0.2, 0.2, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 0.9,
                   0.8, 0.8, 0.8, 0.9, 1.0, 1.2, 1.3, 1.2, 1.0, 0.8, 0.6, 0.4]
    else:
        profile = [0.2, 0.2, 0.2, 0.2, 0.2, 0.4, 0.8, 1.2, 1.0, 0.7, 0.6, 0.6,
                   0.7, 0.6, 0.6, 0.7, 0.9, 1.3, 1.4, 1.3, 1.1, 0.8, 0.5, 0.3]
    return profile[hour]


def is_peak(ts: datetime) -> bool:
    h = ts.hour
    return (6 <= h < 10) or (18 <= h < 22)


def get_rate(ts: datetime) -> float:
    h = ts.hour
    if (6 <= h < 10) or (18 <= h < 22):
        return 9.50
    if 10 <= h < 18:
        return 6.50
    return 4.00


async def seed(n_households: int = 50, days: int = 365):
    from shems.database import AsyncSessionLocal
    from shems.domains.auth.models import PersonaType, User
    from shems.core.security.password import hash_password
    from shems.domains.grid.models import GridZone
    from shems.domains.tariff.models import TariffZone, RateWindow, WindowType
    from shems.domains.household.models import (
        Device, DeviceType, EcosystemType, EnergyReading, Household, ReadingSource,
    )

    async with AsyncSessionLocal() as db:
        print("🌱 Seeding SHEMS development data...")

        # ── Demo users ────────────────────────────────────────────────────────
        demo_users = [
            ("sarah@shems.dev", PersonaType.HOMEOWNER, "Sarah Demo"),
            ("marcus@shems.dev", PersonaType.RENTER, "Marcus Demo"),
            ("priya@shems.dev", PersonaType.GRID_MANAGER, "Priya Demo"),
        ]
        created_users = []
        for email, persona, name in demo_users:
            user = User(
                email=email,
                hashed_password=hash_password("demo1234"),
                persona_type=persona,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            created_users.append(user)
        await db.commit()
        print(f"  ✓ Created {len(demo_users)} demo users (password: demo1234)")

        # ── Grid zones ────────────────────────────────────────────────────────
        grid_zones = []
        for d in DISTRICTS:
            zone = GridZone(
                zone_name=d["name"],
                district_code=d["code"],
                city=d["city"],
                peak_capacity_kw=d["peak_kw"],
                total_households=n_households // len(DISTRICTS),
            )
            db.add(zone)
            grid_zones.append(zone)
        await db.commit()
        print(f"  ✓ Created {len(grid_zones)} grid zones")

        # ── Tariff zones ──────────────────────────────────────────────────────
        tariff_zones = []
        for gz in grid_zones:
            tz = TariffZone(
                district_id=gz.id,
                zone_name=f"{gz.zone_name} Tariff",
                utility_provider=f"{gz.city} City Power",
                currency="INR",
            )
            db.add(tz)
            tariff_zones.append(tz)
        await db.commit()

        # Rate windows for each tariff zone
        today = date.today()
        for tz in tariff_zones:
            for rw in RATE_WINDOWS:
                start = rw["start"]
                end = rw["end"]
                # Handle overnight window
                window = RateWindow(
                    tariff_zone_id=tz.id,
                    window_type=WindowType(rw["type"]),
                    start_time=start,
                    end_time=end,
                    days_of_week=rw["days"],
                    rate_per_kwh=rw["rate"],
                    effective_from=date(2024, 1, 1),
                    effective_until=None,
                )
                db.add(window)
        await db.commit()
        print(f"  ✓ Created {len(tariff_zones)} tariff zones with rate windows")

        # ── Households + devices ──────────────────────────────────────────────
        households = []
        for i in range(n_households):
            gz = random.choice(grid_zones)
            meter_id = f"MTR{i + 1:05d}"
            address = fake.address()
            addr_hash = hashlib.sha256(address.encode()).hexdigest()

            h = Household(
                user_id=created_users[0].id if i == 0 else created_users[1].id if i == 1 else uuid.uuid4(),
                address_hash=addr_hash,
                district_id=gz.id,
                smart_meter_id=meter_id,
                ecosystem_type=random.choice(list(EcosystemType)),
                square_footage=random.randint(600, 3000),
                occupant_count=random.randint(1, 6),
            )
            # For households beyond demo users, create a synthetic user_id
            if i > 1:
                u = User(
                    email=f"household_{i}@synthetic.shems",
                    hashed_password=hash_password("synthetic"),
                    persona_type=random.choice([PersonaType.HOMEOWNER, PersonaType.RENTER]),
                    is_active=True,
                    is_verified=False,
                )
                db.add(u)
                await db.flush()
                h.user_id = u.id
            db.add(h)
            households.append(h)
        await db.commit()
        print(f"  ✓ Created {n_households} households")

        # Add devices to first 20 households
        for h in households[:20]:
            n_devices = random.randint(2, 5)
            for tpl in random.sample(DEVICE_TEMPLATES, n_devices):
                dev = Device(
                    household_id=h.id,
                    name=tpl["name"],
                    device_type=DeviceType(tpl["type"]),
                    rated_power_watts=float(tpl["watts"]),
                    is_schedulable=tpl["schedulable"],
                    ecosystem=h.ecosystem_type,
                )
                db.add(dev)
        await db.commit()
        print("  ✓ Added devices to first 20 households")

        # ── Energy readings ───────────────────────────────────────────────────
        print(f"  ⏳ Generating {days} days of 15-min readings for {n_households} households...")
        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(days=days)

        batch = []
        total_readings = 0
        BATCH_SIZE = 5000

        for h in households:
            base_kwh = random.uniform(0.2, 1.5)  # household baseline
            ts = start_dt

            while ts < now:
                is_weekend = ts.weekday() >= 5
                multiplier = consumption_profile(ts.hour, is_weekend)
                noise = random.gauss(1.0, 0.1)
                kwh = max(0.01, base_kwh * multiplier * noise / 4)  # /4 for 15-min interval
                rate = get_rate(ts)

                batch.append(EnergyReading(
                    household_id=h.id,
                    timestamp=ts,
                    consumption_kwh=round(kwh, 4),
                    cost_estimate_inr=round(kwh * rate, 4),
                    is_peak_hour=is_peak(ts),
                    source=ReadingSource.SMART_METER,
                ))
                ts += timedelta(minutes=15)

                if len(batch) >= BATCH_SIZE:
                    db.add_all(batch)
                    await db.commit()
                    total_readings += len(batch)
                    batch = []
                    print(f"    ... {total_readings:,} readings inserted", end="\r")

        if batch:
            db.add_all(batch)
            await db.commit()
            total_readings += len(batch)

        print(f"\n  ✓ Inserted {total_readings:,} energy readings")
        print("\n✅ Seed complete!")
        print(f"\nDemo accounts:")
        print(f"  sarah@shems.dev   (HOMEOWNER)    password: demo1234")
        print(f"  marcus@shems.dev  (RENTER)        password: demo1234")
        print(f"  priya@shems.dev   (GRID_MANAGER)  password: demo1234")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed SHEMS development data")
    parser.add_argument("--households", type=int, default=50, help="Number of households to generate")
    parser.add_argument("--days", type=int, default=365, help="Days of historical readings to generate")
    args = parser.parse_args()

    asyncio.run(seed(n_households=args.households, days=args.days))
