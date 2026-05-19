from __future__ import annotations

from typing import Protocol

from snf_schedule_optimizer.models import (
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSnapshot,
    Schedule,
)
from snf_schedule_optimizer.persistence.unit_of_work import UnitOfWorkFactory
from snf_schedule_optimizer.service.scheduling.commands import (
    ClaimOptimizationRunHandler,
    CompleteOptimizationRunHandler,
    FailOptimizationRunHandler,
    PublishOptimizationProgressHandler,
    RenewOptimizationRunLeaseHandler,
    SaveSnapshotWithRunHandler,
)


class IOptimizationWorkerStore(Protocol):
    async def claim_next_queued_optimization_run(
        self,
        worker_id: str,
        claim_token: str,
        lease_expires_at: str,
    ) -> OptimizationRun | None: ...

    async def renew_optimization_run_lease(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool: ...

    async def publish_progress(
        self,
        run: OptimizationRun,
        event: OptimizationRunEvent,
    ) -> None: ...

    async def save_snapshot_with_run(
        self,
        snapshot: OptimizationSnapshot,
        run: OptimizationRun,
    ) -> None: ...

    async def complete_run(
        self,
        run_id: str,
        claim_token: str,
        run: OptimizationRun,
        event: OptimizationRunEvent,
        result_schedule: Schedule | None = None,
    ) -> None: ...

    async def fail_run(
        self,
        run_id: str,
        claim_token: str,
        stage: str,
        status_message: str,
        error_details: str | None,
        failure_code: str,
        final_sequence: int,
    ) -> None: ...


class SqlOptimizationWorkerStore:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._claim_handler = ClaimOptimizationRunHandler(uow_factory)
        self._renew_handler = RenewOptimizationRunLeaseHandler(uow_factory)
        self._publish_handler = PublishOptimizationProgressHandler(uow_factory)
        self._snapshot_handler = SaveSnapshotWithRunHandler(uow_factory)
        self._complete_handler = CompleteOptimizationRunHandler(uow_factory)
        self._fail_handler = FailOptimizationRunHandler(uow_factory)

    async def claim_next_queued_optimization_run(
        self,
        worker_id: str,
        claim_token: str,
        lease_expires_at: str,
    ) -> OptimizationRun | None:
        return await self._claim_handler.execute(
            worker_id=worker_id,
            claim_token=claim_token,
            lease_expires_at=lease_expires_at,
        )

    async def renew_optimization_run_lease(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool:
        return await self._renew_handler.execute(
            run_id=run_id,
            claim_token=claim_token,
            heartbeat_at=heartbeat_at,
            lease_expires_at=lease_expires_at,
        )

    async def publish_progress(
        self,
        run: OptimizationRun,
        event: OptimizationRunEvent,
    ) -> None:
        await self._publish_handler.execute(run=run, event=event)

    async def save_snapshot_with_run(
        self,
        snapshot: OptimizationSnapshot,
        run: OptimizationRun,
    ) -> None:
        await self._snapshot_handler.execute(snapshot=snapshot, run=run)

    async def complete_run(
        self,
        run_id: str,
        claim_token: str,
        run: OptimizationRun,
        event: OptimizationRunEvent,
        result_schedule: Schedule | None = None,
    ) -> None:
        await self._complete_handler.execute(
            run_id=run_id,
            claim_token=claim_token,
            run=run,
            event=event,
            result_schedule=result_schedule,
        )

    async def fail_run(
        self,
        run_id: str,
        claim_token: str,
        stage: str,
        status_message: str,
        error_details: str | None,
        failure_code: str,
        final_sequence: int,
    ) -> None:
        await self._fail_handler.execute(
            run_id=run_id,
            claim_token=claim_token,
            stage=stage,
            status_message=status_message,
            error_details=error_details,
            failure_code=failure_code,
            final_sequence=final_sequence,
        )
