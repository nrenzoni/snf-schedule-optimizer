"""Unit tests for ScheduleQueryService."""
from unittest.mock import AsyncMock

import whenever

from snf_schedule_optimizer.domain.repositories import IFacilityRepo, IShiftRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IOptimizationRunRepo,
    IScheduleRepo,
)
from snf_schedule_optimizer.models import OptimizationRun
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.service.scheduling.queries import ScheduleQueryService


class TestScheduleQueryService:
    async def test_get_optimization_run_delegates(self) -> None:
        schedule_repo = AsyncMock(spec=IScheduleRepo)
        run_repo = AsyncMock(spec=IOptimizationRunRepo)
        facility_repo = AsyncMock(spec=IFacilityRepo)
        shift_repo = AsyncMock(spec=IShiftRepo)
        provider_factory = AsyncMock(spec=ScenarioDataProviderFactory)

        expected = OptimizationRun(
            run_id="r1", org_id=1, facility_id=1, schedule_id=10,
            schedule_lineage_id=10, base_schedule_version=1,
            status="completed", stage="completed",
            progress_percent=100, status_message="done",
            started_at=whenever.Instant.now().format_iso(),
        )
        run_repo.get_optimization_run = AsyncMock(return_value=expected)

        svc = ScheduleQueryService(schedule_repo, run_repo, facility_repo, shift_repo, provider_factory)
        result = await svc.get_optimization_run("r1")

        run_repo.get_optimization_run.assert_awaited_once_with("r1")
        assert result is expected

    async def test_get_schedule_status_raises_when_schedule_missing(self) -> None:
        schedule_repo = AsyncMock(spec=IScheduleRepo)
        run_repo = AsyncMock(spec=IOptimizationRunRepo)
        facility_repo = AsyncMock(spec=IFacilityRepo)
        shift_repo = AsyncMock(spec=IShiftRepo)
        provider_factory = AsyncMock(spec=ScenarioDataProviderFactory)

        schedule_repo.get_schedule = AsyncMock(return_value=None)

        svc = ScheduleQueryService(schedule_repo, run_repo, facility_repo, shift_repo, provider_factory)
        try:
            await svc.get_schedule_status(1, 1, 10, 0)
            raise AssertionError("Expected ValueError")
        except ValueError:
            pass
