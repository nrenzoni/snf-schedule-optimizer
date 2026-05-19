from __future__ import annotations

from typing import Protocol

import whenever
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from snf_schedule_optimizer.models import (
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSnapshot,
    Schedule,
)
from snf_schedule_optimizer.persistence.schedule_repo import SQLScheduleRepo


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
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def claim_next_queued_optimization_run(
        self,
        worker_id: str,
        claim_token: str,
        lease_expires_at: str,
    ) -> OptimizationRun | None:
        async with self._session_factory() as session:
            repo = SQLScheduleRepo(db_session=session)
            run = await repo.claim_next_queued_optimization_run(
                worker_id=worker_id,
                claim_token=claim_token,
                lease_expires_at=lease_expires_at,
            )
            if run is not None:
                await session.commit()
            return run

    async def renew_optimization_run_lease(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool:
        async with self._session_factory() as session:
            repo = SQLScheduleRepo(db_session=session)
            renewed = await repo.renew_optimization_run_lease(
                run_id=run_id,
                claim_token=claim_token,
                heartbeat_at=heartbeat_at,
                lease_expires_at=lease_expires_at,
            )
            if renewed:
                await session.commit()
            return renewed

    async def publish_progress(
        self,
        run: OptimizationRun,
        event: OptimizationRunEvent,
    ) -> None:
        async with self._session_factory() as session:
            repo = SQLScheduleRepo(db_session=session)
            await repo.save_optimization_run(run)
            await repo.append_optimization_run_event(event)
            await session.commit()

    async def save_snapshot_with_run(
        self,
        snapshot: OptimizationSnapshot,
        run: OptimizationRun,
    ) -> None:
        async with self._session_factory() as session:
            repo = SQLScheduleRepo(db_session=session)
            await repo.save_optimization_snapshot(snapshot)
            await repo.save_optimization_run(run)
            await session.commit()

    async def complete_run(
        self,
        run_id: str,
        claim_token: str,
        run: OptimizationRun,
        event: OptimizationRunEvent,
        result_schedule: Schedule | None = None,
    ) -> None:
        async with self._session_factory() as session:
            repo = SQLScheduleRepo(db_session=session)
            await repo.save_optimization_run(run)
            await repo.append_optimization_run_event(event)
            if result_schedule is not None:
                await repo.save_schedule(result_schedule)
            await repo.release_optimization_run_claim(
                run_id=run_id,
                claim_token=claim_token,
                status="completed",
                stage="completed",
                status_message="Optimization completed",
            )
            await session.commit()

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
        async with self._session_factory() as session:
            repo = SQLScheduleRepo(db_session=session)
            await repo.append_optimization_run_event(
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
            await repo.release_optimization_run_claim(
                run_id=run_id,
                claim_token=claim_token,
                status="failed",
                stage=stage,
                status_message=status_message,
                error_details=error_details,
                failure_code=failure_code,
            )
            await session.commit()
