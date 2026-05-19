"""Unit tests for optimization command handlers."""

from unittest.mock import AsyncMock, MagicMock

import whenever

from snf_schedule_optimizer.models import (
    OptimizationRun,
    OptimizationRunEvent,
    Schedule,
)
from snf_schedule_optimizer.persistence.unit_of_work import UnitOfWorkFactory
from snf_schedule_optimizer.service.scheduling.commands import (
    PersistOptimizedScheduleHandler,
    StartOptimizationRunHandler,
)


class TestStartOptimizationRunHandler:
    async def test_execute_opens_uow_saves_and_commits(self) -> None:
        mock_uow = AsyncMock()
        mock_uow.optimization_run_repo = AsyncMock()
        mock_uow.commit = AsyncMock()
        mock_factory = MagicMock(spec=UnitOfWorkFactory)
        mock_factory.return_value.__aenter__.return_value = mock_uow
        mock_factory.return_value.__aexit__.return_value = None

        handler = StartOptimizationRunHandler(mock_factory)
        run = OptimizationRun(
            run_id="test-run",
            org_id=1,
            facility_id=1,
            schedule_id=10,
            schedule_lineage_id=10,
            base_schedule_version=1,
            status="queued",
            stage="queued",
            progress_percent=0,
            status_message="queued",
            started_at=whenever.Instant.now().format_iso(),
        )
        event = OptimizationRunEvent(
            run_id="test-run",
            sequence=0,
            status="queued",
            stage="queued",
            progress_percent=0,
            status_message="queued",
            created_at=whenever.Instant.now().format_iso(),
        )

        result = await handler.execute(run, event)

        mock_uow.optimization_run_repo.save_optimization_run.assert_awaited_once_with(
            run
        )
        mock_uow.optimization_run_repo.append_optimization_run_event.assert_awaited_once_with(
            event
        )
        mock_uow.commit.assert_awaited_once()
        assert result is run


class TestPersistOptimizedScheduleHandler:
    async def test_execute_opens_uow_saves_and_commits(self) -> None:
        mock_uow = AsyncMock()
        mock_uow.schedule_repo = AsyncMock()
        mock_uow.commit = AsyncMock()
        mock_factory = MagicMock(spec=UnitOfWorkFactory)
        mock_factory.return_value.__aenter__.return_value = mock_uow
        mock_factory.return_value.__aexit__.return_value = None

        handler = PersistOptimizedScheduleHandler(mock_factory)
        schedule = Schedule(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            schedule_lineage_id=10,
            schedule_version=1,
            shift_assignments={},
            start_date="2025-01-01",
            end_date="2025-01-31",
            updated_at=whenever.Instant.now().format_iso(),
        )

        await handler.execute(schedule)

        mock_uow.schedule_repo.save_schedule.assert_awaited_once_with(schedule)
        mock_uow.commit.assert_awaited_once()


class TestCommandHandlerRollback:
    async def test_start_run_rollback_on_exception(self) -> None:
        mock_uow = AsyncMock()
        mock_uow.optimization_run_repo = AsyncMock()
        mock_uow.optimization_run_repo.save_optimization_run = AsyncMock(
            side_effect=RuntimeError("db error")
        )
        mock_uow.commit = AsyncMock()
        mock_factory = MagicMock(spec=UnitOfWorkFactory)
        mock_factory.return_value.__aenter__.return_value = mock_uow
        mock_factory.return_value.__aexit__.return_value = None

        handler = StartOptimizationRunHandler(mock_factory)
        run = OptimizationRun(
            run_id="test-run",
            org_id=1,
            facility_id=1,
            schedule_id=10,
            schedule_lineage_id=10,
            base_schedule_version=1,
            status="queued",
            stage="queued",
            progress_percent=0,
            status_message="queued",
            started_at=whenever.Instant.now().format_iso(),
        )
        event = OptimizationRunEvent(
            run_id="test-run",
            sequence=0,
            status="queued",
            stage="queued",
            progress_percent=0,
            status_message="queued",
            created_at=whenever.Instant.now().format_iso(),
        )

        try:
            await handler.execute(run, event)
            raise AssertionError("Expected RuntimeError")
        except RuntimeError:
            pass

        mock_uow.commit.assert_not_called()
