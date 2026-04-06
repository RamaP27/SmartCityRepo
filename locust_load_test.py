"""
Locust load test scenarios for SHEMS API (Phase 4 — Week 14).

Simulates three concurrent user types:
  - HomeownerUser   (Sarah / Marcus) — 70% of traffic
  - GridManagerUser (Priya)          — 20% of traffic
  - IngestUser      (smart meters)   — 10% of traffic (high frequency, low payload)

Run:
    pip install locust
    locust -f scripts/locust_load_test.py \
        --host http://localhost:8000 \
        --users 100 \
        --spawn-rate 10 \
        --run-time 5m \
        --headless

Targets (from Phase 4 SLA):
  - /api/v1/households/me/readings   p95 < 200ms
  - /api/v1/grid/zones/{id}/summary  p95 < 150ms  (cached)
  - /api/v1/ingest/meter-reading     p95 < 100ms  (write path)
"""
from __future__ import annotations

import json
import random
import uuid

from locust import HttpUser, TaskSet, between, task

# ── Shared test data ──────────────────────────────────────────────────────────
# Pre-seeded demo accounts (created by scripts/seed_synthetic_data.py)
_HOMEOWNER_CREDS = {"email": "sarah@shems.dev",  "password": "demo1234"}
_RENTER_CREDS    = {"email": "marcus@shems.dev", "password": "demo1234"}
_GRID_MGR_CREDS  = {"email": "priya@shems.dev",  "password": "demo1234"}

_FAKE_METER_IDS = [f"METER{str(i).zfill(4)}" for i in range(1, 51)]
_FAKE_ZONE_IDS: list[str] = []   # populated after first grid API call


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Homeowner task set ────────────────────────────────────────────────────────

class HomeownerTasks(TaskSet):
    token: str = ""

    def on_start(self):
        creds = random.choice([_HOMEOWNER_CREDS, _RENTER_CREDS])
        resp = self.client.post("/api/v1/auth/login", json=creds)
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")

    @task(5)
    def get_household(self):
        self.client.get(
            "/api/v1/households/me",
            headers=_auth_header(self.token),
            name="/households/me",
        )

    @task(8)
    def get_readings(self):
        self.client.get(
            "/api/v1/households/me/readings?granularity=1h",
            headers=_auth_header(self.token),
            name="/households/me/readings",
        )

    @task(3)
    def get_sustainability(self):
        self.client.get(
            "/api/v1/sustainability/me",
            headers=_auth_header(self.token),
            name="/sustainability/me",
        )

    @task(4)
    def get_billing_usage(self):
        self.client.get(
            "/api/v1/billing/me/usage?period=month",
            headers=_auth_header(self.token),
            name="/billing/me/usage",
        )

    @task(2)
    def get_tariff(self):
        self.client.get(
            "/api/v1/tariff/zones",
            headers=_auth_header(self.token),
            name="/tariff/zones",
        )

    @task(1)
    def ai_schedule_suggest(self):
        self.client.get(
            "/api/v1/households/me/schedules/ai-suggest",
            headers=_auth_header(self.token),
            name="/households/me/schedules/ai-suggest",
        )

    @task(2)
    def get_spending_alerts(self):
        self.client.get(
            "/api/v1/billing/me/alerts/active",
            headers=_auth_header(self.token),
            name="/billing/me/alerts/active",
        )


# ── Grid manager task set ─────────────────────────────────────────────────────

class GridManagerTasks(TaskSet):
    token: str = ""
    zone_ids: list[str] = []

    def on_start(self):
        resp = self.client.post("/api/v1/auth/login", json=_GRID_MGR_CREDS)
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        # Fetch zone list
        zones_resp = self.client.get(
            "/api/v1/grid/zones",
            headers=_auth_header(self.token),
        )
        if zones_resp.status_code == 200:
            self.zone_ids = [z["id"] for z in zones_resp.json()]

    def _rand_zone(self) -> str:
        return random.choice(self.zone_ids) if self.zone_ids else str(uuid.uuid4())

    @task(6)
    def zone_summary(self):
        zone_id = self._rand_zone()
        self.client.get(
            f"/api/v1/grid/zones/{zone_id}/summary",
            headers=_auth_header(self.token),
            name="/grid/zones/{id}/summary",
        )

    @task(4)
    def latest_forecasts(self):
        zone_id = self._rand_zone()
        self.client.get(
            f"/api/v1/grid/zones/{zone_id}/forecasts",
            headers=_auth_header(self.token),
            name="/grid/zones/{id}/forecasts",
        )

    @task(3)
    def zone_alerts(self):
        zone_id = self._rand_zone()
        self.client.get(
            f"/api/v1/grid/zones/{zone_id}/alerts?unacknowledged_only=true",
            headers=_auth_header(self.token),
            name="/grid/zones/{id}/alerts",
        )

    @task(2)
    def ml_models(self):
        self.client.get(
            "/api/v1/ml/models",
            headers=_auth_header(self.token),
            name="/ml/models",
        )

    @task(1)
    def forecast_history(self):
        zone_id = self._rand_zone()
        self.client.get(
            f"/api/v1/grid/zones/{zone_id}/forecasts/history?horizon_hours=1",
            headers=_auth_header(self.token),
            name="/grid/zones/{id}/forecasts/history",
        )


# ── Smart meter ingest task set ───────────────────────────────────────────────

class IngestTasks(TaskSet):
    @task(10)
    def ingest_meter_reading(self):
        payload = {
            "smart_meter_id": random.choice(_FAKE_METER_IDS),
            "timestamp": "2026-03-23T12:00:00Z",
            "consumption_kwh": round(random.uniform(0.05, 3.5), 4),
            "source": "SMART_METER",
        }
        self.client.post(
            "/api/v1/ingest/meter-reading",
            json=payload,
            name="/ingest/meter-reading",
        )

    @task(3)
    def ingest_grid_load(self):
        payload = {
            "zone_id": str(uuid.uuid4()),
            "timestamp": "2026-03-23T12:00:00Z",
            "current_load_kw": round(random.uniform(100, 450), 1),
            "capacity_utilization_pct": round(random.uniform(20, 95), 1),
            "source": "SCADA",
        }
        self.client.post(
            "/api/v1/ingest/grid-load",
            json=payload,
            name="/ingest/grid-load",
        )


# ── User classes ──────────────────────────────────────────────────────────────

class HomeownerUser(HttpUser):
    tasks = [HomeownerTasks]
    weight = 70
    wait_time = between(1, 5)


class GridManagerUser(HttpUser):
    tasks = [GridManagerTasks]
    weight = 20
    wait_time = between(2, 8)


class IngestUser(HttpUser):
    tasks = [IngestTasks]
    weight = 10
    wait_time = between(0.5, 2)
