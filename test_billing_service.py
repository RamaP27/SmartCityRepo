"""
Unit tests for BillingService — all database calls mocked via AsyncMock.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shems.domains.billing.models import AlertType, BillingAccount, NotificationChannel, OverageAlert, SpendingCap, UsageSummary
from shems.domains.billing.schemas import BillingAccountCreate, BillingAccountUpdate, SpendingCapCreate
from shems.domains.billing.service import BillingService
from shems.exceptions import AlreadyExistsException, NotFoundException

# ── Fixtures ──────────────────────────────────────────────────────────────────

USER_ID = uuid.uuid4()
ACCOUNT_ID = uuid.uuid4()
NOW = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)


def _make_account(**kwargs) -> BillingAccount:
    a = MagicMock(spec=BillingAccount)
    a.id = kwargs.get("id", ACCOUNT_ID)
    a.user_id = kwargs.get("user_id", USER_ID)
    a.utility_provider = kwargs.get("utility_provider", "BESCOM")
    a.meter_reference = kwargs.get("meter_reference", "MTR001")
    a.billing_cycle_day = kwargs.get("billing_cycle_day", 1)
    a.currency = "INR"
    a.tariff_zone_id = kwargs.get("tariff_zone_id", None)
    a.created_at = NOW
    return a


def _make_cap(**kwargs) -> SpendingCap:
    c = MagicMock(spec=SpendingCap)
    c.id = kwargs.get("id", uuid.uuid4())
    c.billing_account_id = ACCOUNT_ID
    c.monthly_cap_inr = kwargs.get("monthly_cap_inr", 2000.0)
    c.warning_threshold_pct = kwargs.get("warning_threshold_pct", 80.0)
    c.is_active = True
    c.created_at = NOW
    return c


def _make_usage(**kwargs) -> UsageSummary:
    s = MagicMock(spec=UsageSummary)
    s.id = uuid.uuid4()
    s.billing_account_id = ACCOUNT_ID
    s.period_date = kwargs.get("period_date", date(2026, 3, 1))
    s.total_kwh = kwargs.get("total_kwh", 100.0)
    s.peak_kwh = kwargs.get("peak_kwh", 40.0)
    s.off_peak_kwh = kwargs.get("off_peak_kwh", 60.0)
    s.estimated_cost_inr = kwargs.get("estimated_cost_inr", 800.0)
    s.potential_savings_inr = kwargs.get("potential_savings_inr", 150.0)
    return s


def _make_service() -> tuple[BillingService, MagicMock]:
    manager = MagicMock()
    manager.get_by_user_id = AsyncMock()
    manager.get_by_id = AsyncMock()
    manager.create_account = AsyncMock()
    manager.update_account = AsyncMock()
    manager.create_cap = AsyncMock()
    manager.get_active_cap = AsyncMock()
    manager.list_alerts = AsyncMock()
    manager.get_usage_summaries = AsyncMock()
    manager.get_month_total_spend = AsyncMock()
    manager.get_recent_alert = AsyncMock()
    manager.create_alert = AsyncMock()
    service = BillingService(manager=manager)
    return service, manager


# ── create_account ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_account_success():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = None
    account = _make_account()
    mgr.create_account.return_value = account

    request = BillingAccountCreate(utility_provider="BESCOM", billing_cycle_day=1)
    result = await service.create_account(USER_ID, request)

    mgr.create_account.assert_awaited_once()
    assert result.utility_provider == "BESCOM"


@pytest.mark.asyncio
async def test_create_account_duplicate_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()

    request = BillingAccountCreate(utility_provider="BESCOM", billing_cycle_day=1)
    with pytest.raises(AlreadyExistsException):
        await service.create_account(USER_ID, request)

    mgr.create_account.assert_not_awaited()


# ── get_account ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_account_found():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()

    result = await service.get_account(USER_ID)
    assert result.user_id == USER_ID


@pytest.mark.asyncio
async def test_get_account_not_found_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = None

    with pytest.raises(NotFoundException):
        await service.get_account(USER_ID)


# ── update_account ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_account_propagates_fields():
    service, mgr = _make_service()
    account = _make_account()
    mgr.get_by_user_id.return_value = account
    updated = _make_account(utility_provider="TATA Power")
    mgr.update_account.return_value = updated

    request = BillingAccountUpdate(utility_provider="TATA Power")
    result = await service.update_account(USER_ID, request)

    mgr.update_account.assert_awaited_once_with(account, utility_provider="TATA Power")
    assert result.utility_provider == "TATA Power"


# ── set_spending_cap ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_spending_cap_success():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    cap = _make_cap(monthly_cap_inr=3000.0)
    mgr.create_cap.return_value = cap

    request = SpendingCapCreate(monthly_cap_inr=3000.0, warning_threshold_pct=80.0)
    result = await service.set_spending_cap(USER_ID, request)

    assert result.monthly_cap_inr == 3000.0


@pytest.mark.asyncio
async def test_set_spending_cap_no_account_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = None

    request = SpendingCapCreate(monthly_cap_inr=1000.0)
    with pytest.raises(NotFoundException):
        await service.set_spending_cap(USER_ID, request)


# ── get_spending_cap ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_spending_cap_returns_cap():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    mgr.get_active_cap.return_value = _make_cap()

    result = await service.get_spending_cap(USER_ID)
    assert result.is_active is True


@pytest.mark.asyncio
async def test_get_spending_cap_none_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    mgr.get_active_cap.return_value = None

    with pytest.raises(NotFoundException):
        await service.get_spending_cap(USER_ID)


# ── get_usage_breakdown ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_usage_breakdown_month():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    summary = _make_usage(total_kwh=200.0, peak_kwh=80.0, off_peak_kwh=120.0,
                          estimated_cost_inr=1600.0, potential_savings_inr=300.0)
    mgr.get_usage_summaries.return_value = [summary]

    result = await service.get_usage_breakdown(USER_ID, period="month")

    assert result.total_kwh == 200.0
    assert result.peak_kwh == 80.0
    assert result.off_peak_kwh == 120.0
    assert result.estimated_cost_inr == 1600.0
    assert result.potential_savings_inr == 300.0


@pytest.mark.asyncio
async def test_usage_breakdown_zero_kwh_no_division_error():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    summary = _make_usage(total_kwh=0.0, peak_kwh=0.0, off_peak_kwh=0.0,
                          estimated_cost_inr=0.0, potential_savings_inr=0.0)
    mgr.get_usage_summaries.return_value = [summary]

    result = await service.get_usage_breakdown(USER_ID, period="month")
    assert result.peak_cost_inr == 0.0


@pytest.mark.asyncio
async def test_usage_breakdown_multiple_summaries_aggregated():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    mgr.get_usage_summaries.return_value = [
        _make_usage(total_kwh=50.0, peak_kwh=20.0, off_peak_kwh=30.0,
                    estimated_cost_inr=400.0, potential_savings_inr=60.0),
        _make_usage(total_kwh=50.0, peak_kwh=20.0, off_peak_kwh=30.0,
                    estimated_cost_inr=400.0, potential_savings_inr=60.0),
    ]

    result = await service.get_usage_breakdown(USER_ID, period="month")
    assert result.total_kwh == 100.0
    assert result.estimated_cost_inr == 800.0


# ── _period_to_dates ──────────────────────────────────────────────────────────

def test_period_today():
    today = date.today()
    from_d, to_d = BillingService._period_to_dates("today")
    assert from_d == to_d == today


def test_period_week():
    from datetime import timedelta
    today = date.today()
    from_d, to_d = BillingService._period_to_dates("week")
    assert from_d == today - timedelta(days=7)
    assert to_d == today


def test_period_month():
    today = date.today()
    from_d, to_d = BillingService._period_to_dates("month")
    assert from_d.day == 1
    assert to_d == today


def test_period_unknown_defaults_to_month():
    today = date.today()
    from_d, to_d = BillingService._period_to_dates("quarter")
    assert from_d.day == 1
    assert to_d == today


# ── check_and_fire_alerts ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_alerts_no_account_exits_early():
    service, mgr = _make_service()
    mgr.get_by_id.return_value = None

    await service.check_and_fire_alerts(ACCOUNT_ID)
    mgr.get_active_cap.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_alerts_no_cap_exits_early():
    service, mgr = _make_service()
    mgr.get_by_id.return_value = _make_account()
    mgr.get_active_cap.return_value = None

    await service.check_and_fire_alerts(ACCOUNT_ID)
    mgr.get_month_total_spend.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_alerts_below_threshold_no_alert():
    service, mgr = _make_service()
    mgr.get_by_id.return_value = _make_account()
    mgr.get_active_cap.return_value = _make_cap(monthly_cap_inr=2000.0, warning_threshold_pct=80.0)
    mgr.get_month_total_spend.return_value = 1000.0  # 50% — below 80% threshold

    await service.check_and_fire_alerts(ACCOUNT_ID)
    mgr.create_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_alerts_warning_threshold_fires_alert():
    service, mgr = _make_service()
    mgr.get_by_id.return_value = _make_account()
    mgr.get_active_cap.return_value = _make_cap(monthly_cap_inr=2000.0, warning_threshold_pct=80.0)
    mgr.get_month_total_spend.return_value = 1700.0  # 85% — above threshold
    mgr.get_recent_alert.return_value = None  # no recent duplicate

    await service.check_and_fire_alerts(ACCOUNT_ID)

    call_kwargs = mgr.create_alert.call_args.kwargs
    assert call_kwargs["alert_type"] == AlertType.WARNING_THRESHOLD


@pytest.mark.asyncio
async def test_check_alerts_cap_reached_fires_alert():
    service, mgr = _make_service()
    mgr.get_by_id.return_value = _make_account()
    mgr.get_active_cap.return_value = _make_cap(monthly_cap_inr=2000.0, warning_threshold_pct=80.0)
    mgr.get_month_total_spend.return_value = 2100.0  # 105% — cap reached
    mgr.get_recent_alert.return_value = None

    await service.check_and_fire_alerts(ACCOUNT_ID)

    call_kwargs = mgr.create_alert.call_args.kwargs
    assert call_kwargs["alert_type"] == AlertType.CAP_REACHED


@pytest.mark.asyncio
async def test_check_alerts_deduplicates_within_one_hour():
    service, mgr = _make_service()
    mgr.get_by_id.return_value = _make_account()
    mgr.get_active_cap.return_value = _make_cap(monthly_cap_inr=2000.0, warning_threshold_pct=80.0)
    mgr.get_month_total_spend.return_value = 1900.0  # above threshold
    # Simulate a recent alert already exists
    mgr.get_recent_alert.return_value = MagicMock()

    await service.check_and_fire_alerts(ACCOUNT_ID)
    mgr.create_alert.assert_not_awaited()


# ── get_savings_tips ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_savings_tips_no_data_returns_default():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    mgr.get_usage_summaries.return_value = []

    tips = await service.get_savings_tips(USER_ID)
    assert len(tips) == 1
    assert "meter" in tips[0].title.lower()


@pytest.mark.asyncio
async def test_savings_tips_with_data_returns_up_to_three():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    mgr.get_usage_summaries.return_value = [_make_usage(peak_kwh=50.0, potential_savings_inr=200.0)]

    tips = await service.get_savings_tips(USER_ID)
    assert len(tips) <= 3
    assert all(t.rank >= 1 for t in tips)


@pytest.mark.asyncio
async def test_savings_tips_ranked_sequentially():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_account()
    mgr.get_usage_summaries.return_value = [_make_usage(peak_kwh=30.0)]

    tips = await service.get_savings_tips(USER_ID)
    for i, tip in enumerate(tips, 1):
        assert tip.rank == i
