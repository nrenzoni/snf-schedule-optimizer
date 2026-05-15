import asyncio
import logging
import os
from contextlib import suppress
from typing import cast

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from that_depends import container_context
from that_depends.providers.context_resources import ContextScopes, SupportsContext

from snf_schedule_optimizer.infrastructure.composition import (
    ISchedulerContainer,
    build_repos_container,
    build_scheduler_container,
)
from snf_schedule_optimizer.persistence.schedule_repo import SQLScheduleRepo
from snf_schedule_optimizer.service.scheduling.optimization_run_worker import (
    POLL_SECONDS,
    OptimizationRunWorker,
)

logger = logging.getLogger("snf_schedule_optimizer.worker")


def _scheduler_context(
    scheduler_container: type[ISchedulerContainer],
) -> SupportsContext[object]:
    return cast(SupportsContext[object], scheduler_container)


async def _renew_lease(
    scheduler_container: type[ISchedulerContainer],
    run_id: str,
    claim_token: str,
    heartbeat_at: str,
    lease_expires_at: str,
) -> bool:
    async with container_context(
        _scheduler_context(scheduler_container),
        scope=ContextScopes.REQUEST,
    ):
        schedule_repo = await scheduler_container.schedule_retriever.resolve()
        renewed = await schedule_repo.renew_optimization_run_lease(
            run_id=run_id,
            claim_token=claim_token,
            heartbeat_at=heartbeat_at,
            lease_expires_at=lease_expires_at,
        )
        if renewed:
            await schedule_repo.commit()
        return renewed


async def run_worker() -> None:
    db_url = os.environ["DATABASE_URL"]
    worker_id = os.getenv("OPTIMIZATION_WORKER_ID", f"worker-{os.getpid()}")

    engine = create_async_engine(db_url, pool_pre_ping=True)
    session_local = async_sessionmaker(bind=engine)
    repos_container = build_repos_container(engine, session_local)
    scheduler_container = build_scheduler_container(repos_container)

    stop_event = asyncio.Event()

    try:
        logger.info("optimization worker started worker_id=%s", worker_id)
        while not stop_event.is_set():
            async with container_context(
                _scheduler_context(scheduler_container),
                scope=ContextScopes.REQUEST,
            ):
                schedule_repo = cast(
                    SQLScheduleRepo,
                    await scheduler_container.schedule_retriever.resolve(),
                )
                scheduler_facade = await scheduler_container.scheduler_service.resolve()
                worker = OptimizationRunWorker(
                    worker_id=worker_id,
                    schedule_repo=schedule_repo,
                    scheduler_facade=scheduler_facade,
                    renew_lease=lambda run_id,
                    claim_token,
                    heartbeat_at,
                    lease_expires_at: _renew_lease(
                        scheduler_container,
                        run_id,
                        claim_token,
                        heartbeat_at,
                        lease_expires_at,
                    ),
                )
                try:
                    claimed = await worker.run_once()
                except Exception:
                    logger.exception(
                        "optimization worker iteration failed worker_id=%s", worker_id
                    )
                    await schedule_repo.rollback()
                    claimed = False
            if not claimed:
                await asyncio.sleep(POLL_SECONDS)
    except asyncio.CancelledError:
        logger.info("optimization worker cancelled worker_id=%s", worker_id)
        raise
    finally:
        stop_event.set()
        await engine.dispose()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    task = asyncio.create_task(run_worker())
    try:
        await task
    except KeyboardInterrupt:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    asyncio.run(main())
