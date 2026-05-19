"""Command handlers for optimization write operations with UoW transaction boundaries."""

from __future__ import annotations

import whenever

from snf_schedule_optimizer.models import (
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSnapshot,
    Schedule,
)
from snf_schedule_optimizer.persistence.unit_of_work import UnitOfWorkFactory


class StartOptimizationRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, run: OptimizationRun, event: OptimizationRunEvent
    ) -> OptimizationRun:
        async with self._uow_factory() as uow:
            await uow.schedule_repo.save_optimization_run(run)
            await uow.schedule_repo.append_optimization_run_event(event)
            await uow.commit()
            return run


class PersistOptimizedScheduleHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, schedule: Schedule) -> None:
        async with self._uow_factory() as uow:
            await uow.schedule_repo.save_schedule(schedule)
            await uow.commit()


class ClaimOptimizationRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        worker_id: str,
        claim_token: str,
        lease_expires_at: str,
    ) -> OptimizationRun | None:
        async with self._uow_factory() as uow:
            run = await uow.schedule_repo.claim_next_queued_optimization_run(
                worker_id=worker_id,
                claim_token=claim_token,
                lease_expires_at=lease_expires_at,
            )
            if run is not None:
                await uow.commit()
            return run


class RenewOptimizationRunLeaseHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool:
        async with self._uow_factory() as uow:
            renewed = await uow.schedule_repo.renew_optimization_run_lease(
                run_id=run_id,
                claim_token=claim_token,
                heartbeat_at=heartbeat_at,
                lease_expires_at=lease_expires_at,
            )
            if renewed:
                await uow.commit()
            return renewed


class PublishOptimizationProgressHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, run: OptimizationRun, event: OptimizationRunEvent
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.schedule_repo.save_optimization_run(run)
            await uow.schedule_repo.append_optimization_run_event(event)
            await uow.commit()


class SaveSnapshotWithRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, snapshot: OptimizationSnapshot, run: OptimizationRun
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.schedule_repo.save_optimization_snapshot(snapshot)
            await uow.schedule_repo.save_optimization_run(run)
            await uow.commit()


class CompleteOptimizationRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        run_id: str,
        claim_token: str,
        run: OptimizationRun,
        event: OptimizationRunEvent,
        result_schedule: Schedule | None = None,
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.schedule_repo.save_optimization_run(run)
            await uow.schedule_repo.append_optimization_run_event(event)
            if result_schedule is not None:
                await uow.schedule_repo.save_schedule(result_schedule)
            await uow.schedule_repo.release_optimization_run_claim(
                run_id=run_id,
                claim_token=claim_token,
                status="completed",
                stage="completed",
                status_message="Optimization completed",
            )
            await uow.commit()


class FailOptimizationRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        run_id: str,
        claim_token: str,
        stage: str,
        status_message: str,
        error_details: str | None,
        failure_code: str,
        final_sequence: int,
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.schedule_repo.append_optimization_run_event(
                OptimizationRunEvent(
                    run_id=run_id,
                    sequence=final_sequence,
                    status="failed",
                    stage=stage,
                    progress_percent=100,
                    status_message=status_message,
                    error_details=error_details,
                    metrics={"failure_code": failure_code},
                    created_at=whenever.Instant.now().format_iso(),
                )
            )
            await uow.schedule_repo.release_optimization_run_claim(
                run_id=run_id,
                claim_token=claim_token,
                status="failed",
                stage=stage,
                status_message=status_message,
                error_details=error_details,
                failure_code=failure_code,
            )
            await uow.commit()
