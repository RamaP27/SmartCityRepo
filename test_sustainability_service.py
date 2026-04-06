"""
Unit tests for SustainabilityService — manager calls mocked via AsyncMock.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shems.domains.sustainability.models import GoalStatus
from shems.domains.sustainability.schemas import CarbonOffsetGoalCreate
from shems.domains.sustainability.service import SustainabilityService
from shems.exceptions import NotFoundException

# ── Fixtures ──────────────────────────────────────────────────────────────────

HH_ID = uuid.uuid4()
GOAL_ID = uuid.uuid4()
NOW = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)


def _make_score(**kwargs) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.household_id = HH_ID
    s.score = kwargs.get("score", 72.5)
    s.grade = kwargs.get("grade", "B")
    s.carbon_kg = kwargs.get("carbon_kg", 180.0)
    s.cluster_key = kwargs.get("cluster_key", "mid_2br")
    s.percentile_rank = kwargs.get("percentile_rank", 0.55)
    s.scored_at = NOW
    return s


def _make_goal(**kwargs) -> MagicMock:
    g = MagicMock()
    g.id = kwargs.get("id", GOAL_ID)
    g.household_id = kwargs.get("household_id", HH_ID)
    g.target_reduction_pct = kwargs.get("target_reduction_pct", 20.0)
    g.target_date = kwargs.get("target_date", date(2026, 12, 31))
    g.baseline_monthly_kwh = kwargs.get("baseline_monthly_kwh", 350.0)
    g.status = kwargs.get("status", GoalStatus.ACTIVE)
    return g


def _make_benchmark(**kwargs) -> MagicMock:
    b = MagicMock()
    b.cluster_key = kwargs.get("cluster_key", "mid_2br")
    b.median_kwh = kwargs.get("median_kwh", 300.0)
    b.p75_kwh = kwargs.get("p75_kwh", 420.0)
    b.sample_size = kwargs.get("sample_size", 150)
    return b


def _make_service() -> tuple[SustainabilityService, MagicMock]:
    """Create SustainabilityService with a mocked manager."""
    mock_db = AsyncMock()
    service = SustainabilityService.__new__(SustainabilityService)
    service.db = mock_db

    mgr = MagicMock()
    mgr.get_latest_score = AsyncMock()
    mgr.get_active_goal = AsyncMock()
    mgr.get_cluster_benchmark = AsyncMock()
    mgr.get_score_history = AsyncMock()
    mgr.create_goal = AsyncMock()
    mgr.update_goal_status = AsyncMock()
    service.mgr = mgr

    return service, mgr


# ── get_summary ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_summary_with_score_and_goal():
    service, mgr = _make_service()
    score = _make_score()
    goal = _make_goal()
    benchmark = _make_benchmark()

    mgr.get_latest_score.return_value = score
    mgr.get_active_goal.return_value = goal
    mgr.get_cluster_benchmark.return_value = benchmark

    result = await service.get_summary(HH_ID)

    assert result.latest_score is score
    assert result.goal is goal
    assert result.cluster_benchmark is benchmark
    assert isinstance(result.tips, list)
    assert len(result.tips) > 0


@pytest.mark.asyncio
async def test_get_summary_no_score_returns_default_tips():
    service, mgr = _make_service()
    mgr.get_latest_score.return_value = None
    mgr.get_active_goal.return_value = None

    result = await service.get_summary(HH_ID)

    assert result.latest_score is None
    assert "Start tracking" in result.tips[0]
    # No cluster benchmark lookup when no score
    mgr.get_cluster_benchmark.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_summary_no_goal_still_works():
    service, mgr = _make_service()
    mgr.get_latest_score.return_value = _make_score()
    mgr.get_active_goal.return_value = None
    mgr.get_cluster_benchmark.return_value = None

    result = await service.get_summary(HH_ID)
    assert result.goal is None


# ── _tips_for_score ───────────────────────────────────────────────────────────

def test_tips_for_none_score():
    tips = SustainabilityService._tips_for_score(None)
    assert len(tips) == 3
    assert any("tracking" in t.lower() for t in tips)


def test_tips_for_a_plus():
    score = _make_score(grade="A+")
    tips = SustainabilityService._tips_for_score(score)
    assert len(tips) == 3
    assert any("top 5%" in t for t in tips)


def test_tips_for_a():
    score = _make_score(grade="A")
    tips = SustainabilityService._tips_for_score(score)
    assert len(tips) == 3
    assert any("A+" in t for t in tips)


def test_tips_for_b():
    score = _make_score(grade="B")
    tips = SustainabilityService._tips_for_score(score)
    assert len(tips) == 3
    assert any("off-peak" in t.lower() for t in tips)


def test_tips_for_c():
    score = _make_score(grade="C")
    tips = SustainabilityService._tips_for_score(score)
    assert len(tips) == 3
    assert any("peak-hour" in t.lower() or "tariff" in t.lower() for t in tips)


def test_tips_for_d():
    score = _make_score(grade="D")
    tips = SustainabilityService._tips_for_score(score)
    assert len(tips) == 3
    assert any("cluster average" in t.lower() for t in tips)


def test_tips_all_grades_return_three_items():
    for grade in ("A+", "A", "B", "C", "D"):
        score = _make_score(grade=grade)
        tips = SustainabilityService._tips_for_score(score)
        assert len(tips) == 3, f"Expected 3 tips for grade {grade}"


# ── get_score_history ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_score_history_delegates_to_manager():
    service, mgr = _make_service()
    history = [_make_score() for _ in range(6)]
    mgr.get_score_history.return_value = history

    result = await service.get_score_history(HH_ID, limit=6)

    mgr.get_score_history.assert_awaited_once_with(HH_ID, limit=6)
    assert result == history


@pytest.mark.asyncio
async def test_get_score_history_default_limit_12():
    service, mgr = _make_service()
    mgr.get_score_history.return_value = []

    await service.get_score_history(HH_ID)
    mgr.get_score_history.assert_awaited_once_with(HH_ID, limit=12)


# ── create_goal ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_goal_calls_manager_and_commits():
    service, mgr = _make_service()
    goal = _make_goal()
    mgr.create_goal.return_value = goal

    data = CarbonOffsetGoalCreate(
        target_reduction_pct=15.0,
        target_date=date(2026, 12, 31),
        baseline_monthly_kwh=350.0,
    )
    result = await service.create_goal(HH_ID, data)

    mgr.create_goal.assert_awaited_once_with(
        household_id=HH_ID,
        target_reduction_pct=15.0,
        target_date=date(2026, 12, 31),
        baseline_monthly_kwh=350.0,
    )
    service.db.commit.assert_awaited_once()
    assert result is goal


# ── cancel_goal ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_goal_success():
    service, mgr = _make_service()
    goal = _make_goal(id=GOAL_ID, household_id=HH_ID, status=GoalStatus.CANCELLED)
    mgr.update_goal_status.return_value = goal

    result = await service.cancel_goal(HH_ID, GOAL_ID)

    mgr.update_goal_status.assert_awaited_once_with(GOAL_ID, GoalStatus.CANCELLED)
    service.db.commit.assert_awaited_once()
    assert result is goal


@pytest.mark.asyncio
async def test_cancel_goal_not_found_raises():
    service, mgr = _make_service()
    mgr.update_goal_status.return_value = None

    with pytest.raises(NotFoundException):
        await service.cancel_goal(HH_ID, GOAL_ID)


@pytest.mark.asyncio
async def test_cancel_goal_wrong_household_raises():
    service, mgr = _make_service()
    other_hh = uuid.uuid4()
    goal = _make_goal(id=GOAL_ID, household_id=other_hh)
    mgr.update_goal_status.return_value = goal

    with pytest.raises(NotFoundException):
        await service.cancel_goal(HH_ID, GOAL_ID)
