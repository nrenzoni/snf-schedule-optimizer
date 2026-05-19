"""Tests for ScheduleReadRepo read-model queries."""

from unittest.mock import AsyncMock, MagicMock

from snf_schedule_optimizer.persistence.read_repo.schedule_read_repo import (
    ScheduleReadRepo,
)


class TestScheduleReadRepo:
    async def test_get_shifts_for_date_range_with_mock(self) -> None:
        session = AsyncMock()
        execute_result = MagicMock()
        execute_result.unique.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=execute_result)
        repo = ScheduleReadRepo(session)
        views = await repo.get_shifts_for_date_range(
            org_id=1,
            facility_id=1,
            start_date="2025-01-01",
            end_date="2025-01-31",
        )
        assert views == []
