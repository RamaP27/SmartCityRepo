"""
Unit tests for HouseholdService — all database calls mocked via AsyncMock.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from shems.domains.household.models import Household
from shems.domains.household.schemas import (
    DeviceCreate,
    DeviceScheduleCreate,
    HouseholdCreate,
    HouseholdUpdate,
)
from shems.domains.household.service import HouseholdService
from shems.exceptions import AlreadyExistsException, ForbiddenException, NotFoundException

# ── Fixtures ──────────────────────────────────────────────────────────────────

USER_ID = uuid.uuid4()
HH_ID = uuid.uuid4()
DEVICE_ID = uuid.uuid4()
SCHED_ID = uuid.uuid4()
NOW = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)


def _make_household(**kwargs) -> MagicMock:
    h = MagicMock(spec=Household)
    h.id = kwargs.get("id", HH_ID)
    h.user_id = kwargs.get("user_id", USER_ID)
    h.address_hash = kwargs.get("address_hash", "abc123")
    h.smart_meter_id = kwargs.get("smart_meter_id", "METER001")
    h.ecosystem_type = kwargs.get("ecosystem_type", "MANUAL")
    h.square_footage = kwargs.get("square_footage", 1200)
    h.occupant_count = kwargs.get("occupant_count", 2)
    h.created_at = NOW
    return h


def _make_device(**kwargs) -> MagicMock:
    d = MagicMock()
    d.id = kwargs.get("id", DEVICE_ID)
    d.household_id = HH_ID
    d.name = kwargs.get("name", "AC Unit")
    d.device_type = kwargs.get("device_type", "AC")
    d.is_schedulable = kwargs.get("is_schedulable", True)
    d.created_at = NOW
    return d


def _make_schedule(**kwargs) -> MagicMock:
    s = MagicMock()
    s.id = kwargs.get("id", SCHED_ID)
    s.device_id = DEVICE_ID
    s.household_id = HH_ID
    s.is_active = True
    return s


def _make_service() -> tuple[HouseholdService, MagicMock]:
    manager = MagicMock()
    manager.get_by_user_id = AsyncMock()
    manager.create = AsyncMock()
    manager.update = AsyncMock()
    manager.list_devices = AsyncMock()
    manager.create_device = AsyncMock()
    manager.get_device = AsyncMock()
    manager.update_device = AsyncMock()
    manager.delete_device = AsyncMock()
    manager.get_readings = AsyncMock()
    manager.list_schedules = AsyncMock()
    manager.create_schedule = AsyncMock()
    manager.get_schedule = AsyncMock()
    manager.deactivate_schedule = AsyncMock()
    service = HouseholdService(manager=manager)
    return service, manager


# ── _hash_address ─────────────────────────────────────────────────────────────

def test_hash_address_produces_sha256():
    address = "123 MG Road, Bengaluru"
    result = HouseholdService._hash_address(address)
    expected = hashlib.sha256(address.encode()).hexdigest()
    assert result == expected
    assert len(result) == 64


def test_hash_address_deterministic():
    addr = "test address"
    assert HouseholdService._hash_address(addr) == HouseholdService._hash_address(addr)


def test_hash_address_different_inputs_differ():
    assert HouseholdService._hash_address("addr1") != HouseholdService._hash_address("addr2")


# ── create_household ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_household_success():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = None
    hh = _make_household()
    mgr.create.return_value = hh

    request = HouseholdCreate(
        address_hash="123 Main St",
        smart_meter_id="METER001",
        ecosystem_type="MANUAL",
        square_footage=1200,
        occupant_count=2,
    )
    result = await service.create_household(USER_ID, request)

    # Verify address was hashed before passing to manager
    call_kwargs = mgr.create.call_args.kwargs
    assert call_kwargs["address_hash"] == hashlib.sha256("123 Main St".encode()).hexdigest()
    assert result.user_id == USER_ID


@pytest.mark.asyncio
async def test_create_household_duplicate_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()

    request = HouseholdCreate(
        address_hash="456 Other St",
        smart_meter_id="METER002",
        ecosystem_type="MANUAL",
    )
    with pytest.raises(AlreadyExistsException):
        await service.create_household(USER_ID, request)

    mgr.create.assert_not_awaited()


# ── get_household ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_household_found():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()

    result = await service.get_household(USER_ID)
    assert result.id == HH_ID


@pytest.mark.asyncio
async def test_get_household_not_found_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = None

    with pytest.raises(NotFoundException):
        await service.get_household(USER_ID)


# ── update_household ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_household_excludes_none():
    service, mgr = _make_service()
    hh = _make_household()
    mgr.get_by_user_id.return_value = hh
    mgr.update.return_value = _make_household(occupant_count=4)

    request = HouseholdUpdate(occupant_count=4)
    result = await service.update_household(USER_ID, request)

    call_kwargs = mgr.update.call_args.kwargs
    assert "occupant_count" in call_kwargs
    # None fields should be excluded
    assert "address_hash" not in call_kwargs


# ── add_device ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_device_success():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    device = _make_device()
    mgr.create_device.return_value = device

    request = DeviceCreate(name="AC Unit", device_type="AC", is_schedulable=True)
    result = await service.add_device(USER_ID, request)

    mgr.create_device.assert_awaited_once()
    assert result.name == "AC Unit"


@pytest.mark.asyncio
async def test_add_device_no_household_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = None

    request = DeviceCreate(name="Washer", device_type="WASHING_MACHINE", is_schedulable=True)
    with pytest.raises(NotFoundException):
        await service.add_device(USER_ID, request)


# ── update_device ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_device_not_found_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    mgr.get_device.return_value = None

    from shems.domains.household.schemas import DeviceUpdate
    request = DeviceUpdate(name="New Name")
    with pytest.raises(NotFoundException):
        await service.update_device(USER_ID, DEVICE_ID, request)


# ── remove_device ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_device_success():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    device = _make_device()
    mgr.get_device.return_value = device

    await service.remove_device(USER_ID, DEVICE_ID)
    mgr.delete_device.assert_awaited_once_with(device)


@pytest.mark.asyncio
async def test_remove_device_not_found_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    mgr.get_device.return_value = None

    with pytest.raises(NotFoundException):
        await service.remove_device(USER_ID, DEVICE_ID)


# ── create_schedule ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_schedule_success():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    device = _make_device(is_schedulable=True)
    mgr.get_device.return_value = device
    schedule = _make_schedule()
    mgr.create_schedule.return_value = schedule

    request = DeviceScheduleCreate(
        start_time="22:00",
        end_time="06:00",
        days_of_week=[0, 1, 2, 3, 4],
        is_active=True,
    )
    result = await service.create_schedule(USER_ID, DEVICE_ID, request)
    assert result.id == SCHED_ID


@pytest.mark.asyncio
async def test_create_schedule_non_schedulable_raises_forbidden():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    device = _make_device(is_schedulable=False)
    mgr.get_device.return_value = device

    request = DeviceScheduleCreate(
        start_time="22:00",
        end_time="06:00",
        days_of_week=[0, 1, 2],
        is_active=True,
    )
    with pytest.raises(ForbiddenException):
        await service.create_schedule(USER_ID, DEVICE_ID, request)


@pytest.mark.asyncio
async def test_create_schedule_device_not_found_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    mgr.get_device.return_value = None

    request = DeviceScheduleCreate(
        start_time="22:00",
        end_time="06:00",
        days_of_week=[0],
        is_active=True,
    )
    with pytest.raises(NotFoundException):
        await service.create_schedule(USER_ID, DEVICE_ID, request)


# ── delete_schedule ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_schedule_success():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    schedule = _make_schedule()
    mgr.get_schedule.return_value = schedule

    await service.delete_schedule(USER_ID, SCHED_ID)
    mgr.deactivate_schedule.assert_awaited_once_with(schedule)


@pytest.mark.asyncio
async def test_delete_schedule_not_found_raises():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = _make_household()
    mgr.get_schedule.return_value = None

    with pytest.raises(NotFoundException):
        await service.delete_schedule(USER_ID, SCHED_ID)


# ── get_or_404 ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_or_404_found_returns_household():
    service, mgr = _make_service()
    hh = _make_household()
    mgr.get_by_user_id.return_value = hh

    result = await service.get_or_404(USER_ID)
    assert result.id == HH_ID


@pytest.mark.asyncio
async def test_get_or_404_missing_raises_not_found():
    service, mgr = _make_service()
    mgr.get_by_user_id.return_value = None

    with pytest.raises(NotFoundException):
        await service.get_or_404(USER_ID)
