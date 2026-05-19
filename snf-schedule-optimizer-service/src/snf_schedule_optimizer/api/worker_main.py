import asyncio
import logging
import os
import signal
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
from snf_schedule_optimizer.infrastructure.logging import (
    configure_logging,
    get_logger,
)
from snf_schedule_optimizer.persistence.unit_of_work import UnitOfWorkFactory
from snf_schedule_optimizer.service.scheduling.optimization_run_worker import (
    POLL_SECONDS,
    OptimizationRunWorker,
)
from snf_schedule_optimizer.service.scheduling.optimization_worker_store import (
    SqlOptimizationWorkerStore,
)

configure_logging()
logger = get_logger(__name__)


def _scheduler_context(
    scheduler_container: type[ISchedulerContainer],
) -> SupportsContext[object]:
    return cast(SupportsContext[object], scheduler_container)


async def _heartbeat_logger(
    worker_id: str,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        logger.info("worker.heartbeat", worker_id=worker_id)
        await asyncio.sleep(60)


async def run_worker() -> None:
    db_url = os.environ["DATABASE_URL"]
    worker_id = os.getenv("OPTIMIZATION_WORKER_ID", f"worker-{os.getpid()}")

    engine = create_async_engine(db_url, pool_pre_ping=True)
    session_local = async_sessionmaker(bind=engine)
    repos_container = build_repos_container(engine, session_local)
    scheduler_container = build_scheduler_container(repos_container)

    stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat_logger(worker_id, stop_event))

    try:
        logger.info("optimization.worker.started", worker_id=worker_id)
        while not stop_event.is_set():
            async with container_context(
                _scheduler_context(scheduler_container),
                scope=ContextScopes.REQUEST,
            ):
                schedule_repo = await scheduler_container.schedule_retriever.resolve()
                scheduler_facade = await scheduler_container.scheduler_service.resolve()
                worker_store = SqlOptimizationWorkerStore(
                    UnitOfWorkFactory(session_local)
                )
                worker = OptimizationRunWorker(
                    worker_id=worker_id,
                    schedule_repo=schedule_repo,
                    scheduler_facade=scheduler_facade,
                    worker_store=worker_store,
                )
                try:
                    claimed = await worker.run_once()
                except Exception:
                    logger.exception(
                        "optimization.worker.iteration_failed",
                        worker_id=worker_id,
                    )
                    claimed = False
            if not claimed:
                await asyncio.sleep(POLL_SECONDS)
    except asyncio.CancelledError:
        logger.info("optimization.worker.cancelled", worker_id=worker_id)
        raise
    finally:
        stop_event.set()
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task
        await engine.dispose()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    task = asyncio.create_task(run_worker())

    loop = asyncio.get_running_loop()

    def _handle_signal() -> None:
        task.cancel()

    loop.add_signal_handler(signal.SIGTERM, _handle_signal)
    loop.add_signal_handler(signal.SIGINT, _handle_signal)

    try:
        await task
    except (KeyboardInterrupt, asyncio.CancelledError):
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    asyncio.run(main())
